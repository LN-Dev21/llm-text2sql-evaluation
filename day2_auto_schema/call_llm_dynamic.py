import argparse
import json
import os
import re
from pathlib import Path

from zai import ZhipuAiClient

from build_prompt import DEFAULT_QUESTION, build_prompt
from extract_schema import DEFAULT_DB, extract_schema


ROOT = Path(__file__).resolve().parent
DEFAULT_PROMPT_OUTPUT = ROOT / "dynamic_prompt.txt"
DEFAULT_SQL_OUTPUT = ROOT / "llm_generated_dynamic.sql"
DEFAULT_METADATA_OUTPUT = ROOT / "llm_dynamic_metadata.json"


def clean_sql(text: str) -> str:
    """Remove an accidental Markdown fence while preserving the SQL itself."""
    value = (text or "").strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fenced:
        value = fenced.group(1).strip()
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="自动读取SQLite Schema，构造Prompt并调用智谱GLM生成SQL"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--prompt-output", type=Path, default=DEFAULT_PROMPT_OUTPUT)
    parser.add_argument("--sql-output", type=Path, default=DEFAULT_SQL_OUTPUT)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT)
    args = parser.parse_args()

    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "未检测到ZAI_API_KEY。请先在当前PowerShell窗口安全设置API密钥。"
        )

    question = args.question.strip()
    if not question:
        raise SystemExit("问题不能为空。")

    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    schema = extract_schema(args.db)
    prompt = build_prompt(schema, question)

    prompt_output = args.prompt_output.resolve()
    prompt_output.parent.mkdir(parents=True, exist_ok=True)
    prompt_output.write_text(prompt, encoding="utf-8")

    client = ZhipuAiClient(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "disabled"},
        temperature=0.0,
        max_tokens=512,
    )

    message = response.choices[0].message
    sql = clean_sql(message.content)
    if not sql:
        reasoning = getattr(message, "reasoning_content", None)
        raise SystemExit(
            "API返回内容为空，未生成SQL。"
            f" finish_reason={response.choices[0].finish_reason!r},"
            f" reasoning_length={len(reasoning or '')}"
        )
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.I):
        raise SystemExit(f"模型返回的内容不像只读SQL，已拒绝保存：\n{sql}")

    sql_output = args.sql_output.resolve()
    sql_output.parent.mkdir(parents=True, exist_ok=True)
    sql_output.write_text(sql.rstrip() + "\n", encoding="utf-8")

    usage = getattr(response, "usage", None)
    metadata = {
        "provider": "Zhipu AI",
        "model": model,
        "database_file": str(args.db.resolve()),
        "question": question,
        "schema_source": "automatically extracted from SQLite",
        "thinking": "disabled",
        "temperature": 0.0,
        "max_tokens": 512,
        "finish_reason": response.choices[0].finish_reason,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "reasoning_length": len(getattr(message, "reasoning_content", None) or ""),
    }
    metadata_output = args.metadata_output.resolve()
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"数据库：{args.db.resolve()}")
    print("Schema来源：从SQLite自动提取")
    print(f"问题：{question}")
    print(f"模型：{model}")
    print(f"动态Prompt已保存：{prompt_output}")
    print(f"SQL已保存：{sql_output}")
    print(sql)


if __name__ == "__main__":
    main()


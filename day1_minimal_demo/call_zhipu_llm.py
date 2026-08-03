import json
import os
import re
from pathlib import Path

from zai import ZhipuAiClient


ROOT = Path(__file__).resolve().parent
PROMPT_FILE = ROOT / "prompt.txt"
SQL_FILE = ROOT / "llm_generated_api.sql"
METADATA_FILE = ROOT / "llm_api_metadata.json"


def clean_sql(text: str) -> str:
    """Remove an accidental Markdown fence while preserving the SQL itself."""
    value = (text or "").strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fenced:
        value = fenced.group(1).strip()
    return value


def main() -> None:
    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "未检测到ZAI_API_KEY。请先在当前PowerShell窗口设置：\n"
            "$env:ZAI_API_KEY = \"你的API密钥\""
        )

    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
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

    SQL_FILE.write_text(sql.rstrip() + "\n", encoding="utf-8")
    usage = getattr(response, "usage", None)
    metadata = {
        "provider": "Zhipu AI",
        "model": model,
        "thinking": "disabled",
        "temperature": 0.0,
        "max_tokens": 512,
        "finish_reason": response.choices[0].finish_reason,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "reasoning_length": len(getattr(message, "reasoning_content", None) or ""),
    }
    METADATA_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"模型：{model}")
    print(f"SQL已保存：{SQL_FILE.name}")
    print(sql)


if __name__ == "__main__":
    main()


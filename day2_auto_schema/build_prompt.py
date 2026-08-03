import argparse
from pathlib import Path

from extract_schema import DEFAULT_DB, extract_schema


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "dynamic_prompt.txt"
DEFAULT_QUESTION = (
    "查询平均成绩超过85分的学生姓名及其平均成绩，"
    "并按照平均成绩从高到低排列。"
)


def build_prompt(schema: str, question: str) -> str:
    """Combine fixed instructions, a live database schema and one question."""
    return f"""你是一个Text-to-SQL助手。请根据给定的SQLite数据库Schema，将自然语言问题转换为一条可执行的SQL查询。

要求：
1. 只输出SQL，不要解释，不要使用Markdown代码块。
2. 只能使用Schema中存在的表和字段。
3. 不要修改数据库，只能生成SELECT查询。

Schema：
{schema}

问题：{question}
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从SQLite自动提取Schema并构造Text-to-SQL Prompt"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    question = args.question.strip()
    if not question:
        raise ValueError("问题不能为空。")

    schema = extract_schema(args.db)
    prompt = build_prompt(schema, question)
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")

    print(f"数据库：{args.db.resolve()}")
    print(f"问题：{question}")
    print(f"动态Prompt已保存：{output_path}")
    print("\n动态Prompt内容：\n")
    print(prompt)


if __name__ == "__main__":
    main()


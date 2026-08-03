import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "student.db"
QUESTION = "查询平均成绩超过85分的学生姓名及其平均成绩，并按照平均成绩从高到低排列。"
EXPECTED_COLUMNS = ["student_name", "average_score"]
EXPECTED_ROWS = [["王五", 93.0], ["张三", 90.0], ["赵六", 88.0]]


def initialize_database() -> None:
    schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
    seed = (ROOT / "seed.sql").read_text(encoding="utf-8")
    with sqlite3.connect(DB_FILE) as connection:
        connection.executescript(schema)
        connection.executescript(seed)


def normalized_rows(rows: list[list[object]]) -> list[list[object]]:
    normalized = []
    for row in rows:
        normalized.append(
            [round(value, 6) if isinstance(value, float) else value for value in row]
        )
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="执行并评测Day 1生成的SQL")
    parser.add_argument("--sql-file", default="llm_generated.sql")
    parser.add_argument("--result-file", default="execution_result.json")
    parser.add_argument("--provider", default="Manual/Codex example")
    args = parser.parse_args()

    sql_path = ROOT / args.sql_file
    result_path = ROOT / args.result_file
    if not sql_path.exists():
        raise SystemExit(f"找不到SQL文件：{sql_path}")

    initialize_database()
    sql = sql_path.read_text(encoding="utf-8").strip()
    result = {
        "question": QUESTION,
        "llm_provider": args.provider,
        "database_file": str(DB_FILE),
        "generated_sql": sql,
        "execution_success": False,
        "columns": [],
        "rows": [],
        "expected_rows": EXPECTED_ROWS,
        "is_correct": False,
        "error": None,
    }

    try:
        if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
            raise ValueError("为保护数据库，本演示只允许执行SELECT或WITH查询。")
        with sqlite3.connect(DB_FILE) as connection:
            cursor = connection.execute(sql)
            result["columns"] = [item[0] for item in cursor.description]
            result["rows"] = [list(row) for row in cursor.fetchall()]
        result["execution_success"] = True
        result["is_correct"] = (
            result["columns"] == EXPECTED_COLUMNS
            and normalized_rows(result["rows"]) == normalized_rows(EXPECTED_ROWS)
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


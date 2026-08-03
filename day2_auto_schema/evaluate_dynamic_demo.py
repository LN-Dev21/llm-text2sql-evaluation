import argparse
import json
import sqlite3
from pathlib import Path

from build_prompt import DEFAULT_QUESTION
from extract_schema import DEFAULT_DB


ROOT = Path(__file__).resolve().parent
DEFAULT_SQL_FILE = ROOT / "llm_generated_dynamic.sql"
DEFAULT_RESULT_FILE = ROOT / "execution_result_dynamic.json"
EXPECTED_COLUMNS = ["student_name", "average_score"]
EXPECTED_ROWS = [["王五", 93.0], ["张三", 90.0], ["赵六", 88.0]]


def normalize_rows(rows: list[list[object]]) -> list[list[object]]:
    normalized: list[list[object]] = []
    for row in rows:
        normalized.append(
            [round(value, 6) if isinstance(value, float) else value for value in row]
        )
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="执行并评测Day 2动态Prompt生成的SQL"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--sql-file", type=Path, default=DEFAULT_SQL_FILE)
    parser.add_argument("--result-file", type=Path, default=DEFAULT_RESULT_FILE)
    args = parser.parse_args()

    db_path = args.db.resolve()
    sql_path = args.sql_file.resolve()
    result_path = args.result_file.resolve()
    if not db_path.is_file():
        raise SystemExit(f"找不到数据库文件：{db_path}")
    if not sql_path.is_file():
        raise SystemExit(f"找不到模型生成的SQL文件：{sql_path}")

    sql = sql_path.read_text(encoding="utf-8").strip()
    result = {
        "question": DEFAULT_QUESTION,
        "llm_provider": "Zhipu GLM dynamic-schema pipeline",
        "schema_source": "automatically extracted from SQLite",
        "database_file": str(db_path),
        "sql_file": str(sql_path),
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
            raise ValueError("为保护数据库，本评测只允许执行SELECT或WITH查询。")

        database_uri = f"{db_path.as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            cursor = connection.execute(sql)
            result["columns"] = [item[0] for item in cursor.description]
            result["rows"] = [list(row) for row in cursor.fetchall()]

        result["execution_success"] = True
        result["is_correct"] = (
            result["columns"] == EXPECTED_COLUMNS
            and normalize_rows(result["rows"]) == normalize_rows(EXPECTED_ROWS)
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


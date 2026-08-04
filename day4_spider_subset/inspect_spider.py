"""检查 Spider 1.0 开发集、元数据与 SQLite 文件是否完整对应。"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DEFAULT_SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
DEFAULT_OUTPUT = DAY_DIR / "dataset_summary.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def database_path(spider_root: Path, db_id: str) -> Path:
    return spider_root / "database" / db_id / f"{db_id}.sqlite"


def inspect_dataset(spider_root: Path) -> dict[str, Any]:
    required = [
        spider_root / "dev.json",
        spider_root / "tables.json",
        spider_root / "database",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Spider 数据不完整，缺少：\n" + "\n".join(missing))

    dev: list[dict[str, Any]] = read_json(spider_root / "dev.json")
    tables: list[dict[str, Any]] = read_json(spider_root / "tables.json")
    metadata = {item["db_id"]: item for item in tables}
    question_counts = collections.Counter(item["db_id"] for item in dev)

    databases: list[dict[str, Any]] = []
    errors: list[str] = []
    for db_id in sorted(question_counts):
        db_path = database_path(spider_root, db_id)
        info = metadata.get(db_id)
        if info is None:
            errors.append(f"{db_id}: tables.json 中没有元数据")
            continue
        if not db_path.is_file():
            errors.append(f"{db_id}: 找不到 {db_path}")
            continue

        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            actual_tables = connection.execute(
                "SELECT COUNT(1) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]

        expected_tables = len(info["table_names_original"])
        if actual_tables != expected_tables:
            errors.append(
                f"{db_id}: 元数据记录 {expected_tables} 张表，SQLite 实际 {actual_tables} 张"
            )

        databases.append(
            {
                "db_id": db_id,
                "question_count": question_counts[db_id],
                "table_count": expected_tables,
                "column_count": len(info["column_names_original"]) - 1,
                "sqlite_file": str(db_path.resolve()),
                "sqlite_size_bytes": db_path.stat().st_size,
            }
        )

    return {
        "dataset": "Spider 1.0 development set",
        "spider_root": str(spider_root.resolve()),
        "question_count": len(dev),
        "database_count": len(question_counts),
        "metadata_database_count": len(tables),
        "validated": not errors,
        "validation_errors": errors,
        "databases": databases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider-root", type=Path, default=DEFAULT_SPIDER_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = inspect_dataset(args.spider_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"开发集问题数：{summary['question_count']}")
    print(f"开发集数据库数：{summary['database_count']}")
    print(f"完整性检查：{'通过' if summary['validated'] else '失败'}")
    print(f"检查报告：{args.output.resolve()}")
    if summary["validation_errors"]:
        for error in summary["validation_errors"]:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

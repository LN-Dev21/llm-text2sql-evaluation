"""记录 Day6 三个数据库的 Schema 规模和 Test Suite 实例数量。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))

from extract_schema import extract_schema  # noqa: E402


SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
TEST_SUITE_ROOT = PROJECT_ROOT / "data" / "test_suite_databases" / "database"
SUBSET_PATH = DAY_DIR / "large_schema_subset.json"
OUTPUT_PATH = DAY_DIR / "schema_profile.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    subset = read_json(SUBSET_PATH)
    table_metadata = {
        item["db_id"]: item for item in read_json(SPIDER_ROOT / "tables.json")
    }
    question_counts: dict[str, int] = {}
    for case in subset["cases"]:
        question_counts[case["db_id"]] = question_counts.get(case["db_id"], 0) + 1

    profiles: list[dict[str, Any]] = []
    for db_id in subset["selection"]["databases"]:
        metadata = table_metadata[db_id]
        db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
        schema = extract_schema(db_path)
        test_suite_folder = TEST_SUITE_ROOT / db_id
        instance_count = len(list(test_suite_folder.glob("*.sqlite")))
        profiles.append(
            {
                "db_id": db_id,
                "selected_question_count": question_counts[db_id],
                "table_count": len(metadata["table_names_original"]),
                "column_count": len(metadata["column_names_original"]) - 1,
                "foreign_key_count": len(metadata["foreign_keys"]),
                "full_schema_character_count": len(schema),
                "full_schema_line_count": len(schema.splitlines()),
                "test_suite_database_instance_count": instance_count,
                "database_file": str(db_path.resolve()),
            }
        )

    report = {
        "experiment": "large-schema controlled comparison",
        "case_count": subset["case_count"],
        "database_count": len(profiles),
        "gold_sql_sent_to_model": False,
        "profiles": profiles,
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Day6 Schema规模：")
    for item in profiles:
        print(
            f"- {item['db_id']}: {item['table_count']}表, "
            f"{item['column_count']}字段, {item['foreign_key_count']}外键, "
            f"{item['selected_question_count']}题, "
            f"{item['test_suite_database_instance_count']}个测试数据库实例"
        )
    print(f"报告：{OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    main()


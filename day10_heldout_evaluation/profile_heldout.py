"""汇总held-out数据库Schema规模、题量和官方增强数据库实例数。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))
from extract_schema import extract_schema  # noqa: E402


SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
TEST_SUITE_ROOT = PROJECT_ROOT / "data" / "test_suite_databases" / "database"


def main() -> None:
    subset = json.loads((DAY_DIR / "heldout_subset.json").read_text(encoding="utf-8"))
    metadata = {item["db_id"]: item for item in json.loads((SPIDER_ROOT / "tables.json").read_text(encoding="utf-8"))}
    counts = {}
    for case in subset["cases"]:
        counts[case["db_id"]] = counts.get(case["db_id"], 0) + 1
    profiles = []
    for db_id in subset["selection"]["databases_and_quotas"]:
        item = metadata[db_id]
        db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
        instances = list((TEST_SUITE_ROOT / db_id).glob("*.sqlite"))
        if not instances:
            raise RuntimeError(f"Test Suite缺少数据库：{db_id}")
        profiles.append({
            "db_id": db_id, "selected_question_count": counts[db_id],
            "table_count": len(item["table_names_original"]),
            "column_count": len(item["column_names_original"])-1,
            "foreign_key_count": len(item["foreign_keys"]),
            "full_schema_character_count": len(extract_schema(db_path)),
            "test_suite_database_instance_count": len(instances),
        })
    report = {"case_count": subset["case_count"], "database_count": len(profiles), "profiles": profiles}
    output = DAY_DIR / "heldout_schema_profile.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Held-out Schema规模：")
    for x in profiles:
        print(f"- {x['db_id']}: {x['table_count']}表, {x['column_count']}字段, "
              f"{x['foreign_key_count']}外键, {x['selected_question_count']}题, "
              f"{x['test_suite_database_instance_count']}个增强数据库")
    print(f"报告：{output.resolve()}")


if __name__ == "__main__":
    main()

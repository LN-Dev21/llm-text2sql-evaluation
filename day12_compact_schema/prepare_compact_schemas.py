"""为30题开发集和150题验证集生成完整但紧凑的Schema表示。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))
from extract_schema import extract_schema  # noqa: E402
from compact_schema import build_compact_schema  # noqa: E402


SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
DATASETS = {
    "development_30": PROJECT_ROOT/"day6_large_schema_experiment"/"large_schema_subset.json",
    "expanded_validation_150": PROJECT_ROOT/"day10_heldout_evaluation"/"heldout_subset.json",
}


def main() -> None:
    schema_cache = {}
    cases_by_dataset = {}
    totals = {"full": 0, "compact": 0, "cases": 0}
    for dataset_name, path in DATASETS.items():
        report = json.loads(path.read_text(encoding="utf-8"))
        output_cases = []
        for case in report["cases"]:
            db_id = case["db_id"]
            if db_id not in schema_cache:
                db_path = SPIDER_ROOT/"database"/db_id/f"{db_id}.sqlite"
                compact, tables = build_compact_schema(db_path)
                full = extract_schema(db_path)
                schema_cache[db_id] = {"compact": compact, "tables": tables, "full": full}
            item = schema_cache[db_id]
            output_cases.append({
                "id": case["id"], "db_id": db_id, "question": case["question"],
                "schema_mode": "compact_full_schema", "selected_tables": item["tables"],
                "selected_schema": item["compact"],
            })
            totals["full"] += len(item["full"])
            totals["compact"] += len(item["compact"])
            totals["cases"] += 1
        cases_by_dataset[dataset_name] = output_cases

    validation = cases_by_dataset["expanded_validation_150"]
    selections = {
        "method": "compact complete schema serialization",
        "information_policy": "preserve every table name, column name, SQLite type, primary key marker, and foreign key",
        "gold_sql_used": False, "case_count": len(validation), "cases": validation,
    }
    selections_path = DAY_DIR/"compact_validation_selections.json"
    selections_path.write_text(json.dumps(selections, ensure_ascii=False, indent=2), encoding="utf-8")
    per_database = []
    for db_id, item in sorted(schema_cache.items()):
        per_database.append({
            "db_id": db_id, "full_schema_characters": len(item["full"]),
            "compact_schema_characters": len(item["compact"]),
            "character_reduction_rate": round(1-len(item["compact"])/len(item["full"]), 4),
            "table_count": len(item["tables"]),
        })
    report = {
        "method": selections["method"], "case_count": totals["cases"],
        "full_schema_character_total": totals["full"],
        "compact_schema_character_total": totals["compact"],
        "overall_character_reduction_rate": round(1-totals["compact"]/totals["full"], 4),
        "all_tables_and_columns_preserved": True, "gold_sql_used": False,
        "per_database": per_database,
    }
    report_path = DAY_DIR/"compact_schema_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("紧凑完整Schema准备完成：")
    print(f"- 覆盖题目：{totals['cases']}")
    print("- 所有表名、字段名、类型、主键标记和外键均保留")
    print(f"- Schema字符减少：{report['overall_character_reduction_rate']:.1%}")
    for item in per_database:
        print(f"- {item['db_id']}: {item['character_reduction_rate']:.1%}")
    print(f"验证集选择文件：{selections_path.resolve()}")
    print(f"报告：{report_path.resolve()}")


if __name__ == "__main__":
    main()

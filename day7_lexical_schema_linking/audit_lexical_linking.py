"""生成词法 Schema Linking 选择文件，并用gold SQL离线审计表覆盖率。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))

from extract_schema import extract_schema  # noqa: E402
from lexical_schema_linker import inspect_database, link_schema  # noqa: E402


DEFAULT_SUBSET = (
    PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
)
DEFAULT_SELECTIONS = DAY_DIR / "lexical_schema_selections.json"
DEFAULT_AUDIT = DAY_DIR / "lexical_schema_audit.json"
SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"


def gold_tables(sql: str, available_tables: list[str]) -> list[str]:
    canonical = {name.lower(): name for name in available_tables}
    candidates = re.findall(
        r"\b(?:FROM|JOIN)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        flags=re.I,
    )
    unknown = sorted({name for name in candidates if name.lower() not in canonical})
    if unknown:
        raise ValueError(f"gold SQL表名解析出现未知项：{unknown}\nSQL: {sql}")
    return sorted({canonical[name.lower()] for name in candidates}, key=str.lower)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--selections", type=Path, default=DEFAULT_SELECTIONS)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--top-k", type=int, default=4)
    args = parser.parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k必须是正整数。")

    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    selections: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    gold_table_total = 0
    covered_table_total = 0
    full_table_total = 0
    selected_table_total = 0
    full_schema_characters = 0
    selected_schema_characters = 0

    for case in subset["cases"]:
        db_id = case["db_id"]
        db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
        tables = inspect_database(db_path)
        linked = link_schema(case["question"], db_path, top_k=args.top_k)
        required_tables = gold_tables(case["gold_sql"], list(tables))
        selected_lookup = {name.lower() for name in linked["selected_tables"]}
        covered = [
            name for name in required_tables if name.lower() in selected_lookup
        ]
        missing = [
            name for name in required_tables if name.lower() not in selected_lookup
        ]
        full_schema = extract_schema(db_path)

        selections.append(
            {
                "id": case["id"],
                "db_id": db_id,
                "question": case["question"],
                "seed_tables": linked["seed_tables"],
                "selected_tables": linked["selected_tables"],
                "selected_schema": linked["selected_schema"],
                "ranked_tables": linked["ranked_tables"],
            }
        )
        audits.append(
            {
                "id": case["id"],
                "db_id": db_id,
                "gold_tables": required_tables,
                "seed_tables": linked["seed_tables"],
                "selected_tables": linked["selected_tables"],
                "missing_gold_tables": missing,
                "all_gold_tables_covered": not missing,
                "full_table_count": linked["full_table_count"],
                "selected_table_count": len(linked["selected_tables"]),
                "full_schema_character_count": len(full_schema),
                "selected_schema_character_count": len(linked["selected_schema"]),
            }
        )
        gold_table_total += len(required_tables)
        covered_table_total += len(covered)
        full_table_total += linked["full_table_count"]
        selected_table_total += len(linked["selected_tables"])
        full_schema_characters += len(full_schema)
        selected_schema_characters += len(linked["selected_schema"])

    case_coverage = sum(item["all_gold_tables_covered"] for item in audits)
    selection_report = {
        "method": "lexical identifier matching + top-k seeds + foreign-key paths",
        "top_k": args.top_k,
        "gold_sql_used_for_selection": False,
        "case_count": len(selections),
        "cases": selections,
    }
    audit_report = {
        "method": selection_report["method"],
        "top_k": args.top_k,
        "important_note": (
            "Gold SQL is used only after selection to audit table coverage; "
            "it is never used by the selector or sent to the model."
        ),
        "case_count": len(audits),
        "all_gold_tables_covered_case_count": case_coverage,
        "case_level_gold_table_coverage": round(case_coverage / len(audits), 4),
        "gold_table_total": gold_table_total,
        "covered_gold_table_total": covered_table_total,
        "micro_gold_table_recall": round(covered_table_total / gold_table_total, 4),
        "average_full_table_count": round(full_table_total / len(audits), 3),
        "average_selected_table_count": round(selected_table_total / len(audits), 3),
        "table_reduction_rate": round(1 - selected_table_total / full_table_total, 4),
        "full_schema_character_total": full_schema_characters,
        "selected_schema_character_total": selected_schema_characters,
        "schema_character_reduction_rate": round(
            1 - selected_schema_characters / full_schema_characters, 4
        ),
        "cases": audits,
    }
    args.selections.write_text(
        json.dumps(selection_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.audit.write_text(
        json.dumps(audit_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("词法 Schema Linking 离线审计：")
    print(f"- Top-K种子表：{args.top_k}")
    print(
        f"- gold表完整覆盖题目：{case_coverage}/{len(audits)} "
        f"({audit_report['case_level_gold_table_coverage']:.1%})"
    )
    print(f"- gold表微平均召回率：{audit_report['micro_gold_table_recall']:.1%}")
    print(
        f"- 平均表数：{audit_report['average_full_table_count']} -> "
        f"{audit_report['average_selected_table_count']}"
    )
    print(f"- 表数量减少：{audit_report['table_reduction_rate']:.1%}")
    print(f"- Schema字符减少：{audit_report['schema_character_reduction_rate']:.1%}")
    print("遗漏gold表的题目：")
    for item in audits:
        if item["missing_gold_tables"]:
            print(
                f"- {item['id']}: missing={item['missing_gold_tables']}, "
                f"selected={item['selected_tables']}"
            )
    print(f"选择文件：{args.selections.resolve()}")
    print(f"审计文件：{args.audit.resolve()}")


if __name__ == "__main__":
    main()

"""比较混合 Schema Linking 配置，固定最佳开发配置并生成选择文件。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
DAY7_DIR = PROJECT_ROOT / "day7_lexical_schema_linking"
sys.path[:0] = [str(DAY2_DIR), str(DAY7_DIR)]

from extract_schema import extract_schema  # noqa: E402
from audit_lexical_linking import gold_tables  # noqa: E402
from hybrid_schema_linker import (  # noqa: E402
    link_schema_hybrid,
    load_embedding_cache,
)
from lexical_schema_linker import inspect_database  # noqa: E402


DEFAULT_SUBSET = PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
DEFAULT_CACHE = DAY_DIR / "embedding_cache.json"
DEFAULT_SELECTIONS = DAY_DIR / "hybrid_schema_selections.json"
DEFAULT_AUDIT = DAY_DIR / "hybrid_schema_audit.json"
DEFAULT_COMPARISON = DAY_DIR / "configuration_comparison.json"
SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"


def evaluate_configuration(
    cases: list[dict[str, Any]], cache: dict[str, Any], top_k: int, lexical_weight: float
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selections, audits = [], []
    totals = {"gold": 0, "covered": 0, "full_tables": 0, "selected_tables": 0,
              "full_chars": 0, "selected_chars": 0}
    for case in cases:
        db_id = case["db_id"]
        db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
        tables = inspect_database(db_path)
        linked = link_schema_hybrid(case["question"], db_path, cache, top_k, lexical_weight)
        required = gold_tables(case["gold_sql"], list(tables))
        selected_lookup = {name.lower() for name in linked["selected_tables"]}
        missing = [name for name in required if name.lower() not in selected_lookup]
        full_schema = extract_schema(db_path)
        selections.append({
            "id": case["id"], "db_id": db_id, "question": case["question"],
            "seed_tables": linked["seed_tables"], "selected_tables": linked["selected_tables"],
            "selected_schema": linked["selected_schema"], "ranked_tables": linked["ranked_tables"],
        })
        audits.append({
            "id": case["id"], "db_id": db_id, "gold_tables": required,
            "seed_tables": linked["seed_tables"], "selected_tables": linked["selected_tables"],
            "missing_gold_tables": missing, "all_gold_tables_covered": not missing,
            "full_table_count": linked["full_table_count"],
            "selected_table_count": len(linked["selected_tables"]),
            "full_schema_character_count": len(full_schema),
            "selected_schema_character_count": len(linked["selected_schema"]),
        })
        totals["gold"] += len(required)
        totals["covered"] += len(required) - len(missing)
        totals["full_tables"] += linked["full_table_count"]
        totals["selected_tables"] += len(linked["selected_tables"])
        totals["full_chars"] += len(full_schema)
        totals["selected_chars"] += len(linked["selected_schema"])
    complete = sum(item["all_gold_tables_covered"] for item in audits)
    metrics = {
        "top_k": top_k,
        "lexical_weight": lexical_weight,
        "semantic_weight": round(1-lexical_weight, 2),
        "complete_coverage_count": complete,
        "case_level_gold_table_coverage": round(complete/len(cases), 4),
        "micro_gold_table_recall": round(totals["covered"]/totals["gold"], 4),
        "average_selected_table_count": round(totals["selected_tables"]/len(cases), 3),
        "table_reduction_rate": round(1-totals["selected_tables"]/totals["full_tables"], 4),
        "schema_character_reduction_rate": round(1-totals["selected_chars"]/totals["full_chars"], 4),
    }
    return metrics, selections, audits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--selections", type=Path, default=DEFAULT_SELECTIONS)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    args = parser.parse_args()
    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    cache = load_embedding_cache(args.cache)
    candidates = []
    payloads = {}
    for top_k in (3, 4, 5):
        for lexical_weight in (0.25, 0.5, 0.75):
            metrics, selections, audits = evaluate_configuration(
                subset["cases"], cache, top_k, lexical_weight
            )
            candidates.append(metrics)
            payloads[(top_k, lexical_weight)] = (selections, audits)

    # 首先最大化完整覆盖和微平均召回；再最大化Schema压缩；最后偏好均衡权重。
    chosen = max(candidates, key=lambda x: (
        x["complete_coverage_count"], x["micro_gold_table_recall"],
        x["schema_character_reduction_rate"], -abs(x["lexical_weight"]-0.5)
    ))
    selections, audits = payloads[(chosen["top_k"], chosen["lexical_weight"])]
    comparison = {
        "embedding_model": cache["model"], "embedding_dimensions": cache["dimensions"],
        "gold_sql_used_for_per_case_scoring": False,
        "gold_sql_used_for_dev_configuration_selection": True,
        "methodological_note": "These 30 cases are used for development-time configuration selection; final model accuracy is an ablation result, not an unbiased held-out estimate.",
        "selection_rule": "maximize complete gold-table coverage, then micro recall, then schema reduction, then prefer weight nearest 0.5",
        "candidates": candidates, "chosen": chosen,
    }
    selection_report = {
        "method": "lexical + embedding-3 table similarity + top-k seeds + foreign-key paths",
        "top_k": chosen["top_k"], "lexical_weight": chosen["lexical_weight"],
        "semantic_weight": chosen["semantic_weight"],
        "gold_sql_used_for_per_case_selection": False, "case_count": len(selections),
        "cases": selections,
    }
    audit_report = {**chosen,
        "important_note": "Gold SQL is used after per-case selection for development configuration audit only; it is never embedded or sent to the LLM.",
        "cases": audits,
    }
    args.comparison.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    args.selections.write_text(json.dumps(selection_report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.audit.write_text(json.dumps(audit_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Exp3混合Schema Linking离线配置比较：")
    for item in candidates:
        print(f"- top_k={item['top_k']}, lexical={item['lexical_weight']:.2f}: "
              f"coverage={item['complete_coverage_count']}/30, recall={item['micro_gold_table_recall']:.1%}, "
              f"schema_reduction={item['schema_character_reduction_rate']:.1%}")
    print("\n固定配置：")
    print(json.dumps(chosen, ensure_ascii=False, indent=2))
    print("遗漏gold表的题目：")
    for item in audits:
        if item["missing_gold_tables"]:
            print(f"- {item['id']}: missing={item['missing_gold_tables']}, selected={item['selected_tables']}")
    print(f"选择文件：{args.selections.resolve()}")


if __name__ == "__main__":
    main()

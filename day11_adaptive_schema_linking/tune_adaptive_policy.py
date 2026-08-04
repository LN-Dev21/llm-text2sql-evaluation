"""在开发集与扩展验证集上离线选择高召回的动态Schema策略。"""

from __future__ import annotations

import itertools
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
from lexical_schema_linker import inspect_database, score_tables  # noqa: E402
from adaptive_schema_linker import apply_adaptive_policy  # noqa: E402


SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
DATASETS = {
    "development_30": PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json",
    "expanded_validation_150": PROJECT_ROOT / "day10_heldout_evaluation" / "heldout_subset.json",
}
COMPARISON = DAY_DIR / "adaptive_configuration_comparison.json"
SELECTIONS = DAY_DIR / "adaptive_validation_selections.json"
AUDIT = DAY_DIR / "adaptive_validation_audit.json"
TARGET_COVERAGE = 0.98


def load_contexts() -> list[dict[str, Any]]:
    database_cache: dict[str, dict[str, Any]] = {}
    contexts = []
    for dataset_name, path in DATASETS.items():
        report = json.loads(path.read_text(encoding="utf-8"))
        for case in report["cases"]:
            db_id = case["db_id"]
            if db_id not in database_cache:
                db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
                tables = inspect_database(db_path)
                database_cache[db_id] = {
                    "db_path": db_path, "tables": tables,
                    "full_schema": extract_schema(db_path),
                }
            cached = database_cache[db_id]
            contexts.append({
                "dataset": dataset_name, "case": case,
                "tables": cached["tables"], "full_schema": cached["full_schema"],
                "rankings": score_tables(case["question"], cached["tables"]),
                "gold_tables": gold_tables(case["gold_sql"], list(cached["tables"])),
            })
    return contexts


def evaluate(contexts: list[dict[str, Any]], config: dict[str, Any], keep_cases: bool = False) -> dict[str, Any]:
    case_rows = []
    totals = {"cases": 0, "complete": 0, "gold": 0, "covered": 0,
              "full_tables": 0, "selected_tables": 0, "full_chars": 0,
              "selected_chars": 0, "fallback": 0}
    dataset_totals: dict[str, dict[str, int]] = {}
    for context in contexts:
        linked = apply_adaptive_policy(
            context["tables"], context["rankings"], context["full_schema"], **config
        )
        selected_lookup = {x.lower() for x in linked["selected_tables"]}
        missing = [x for x in context["gold_tables"] if x.lower() not in selected_lookup]
        dataset = context["dataset"]
        ds = dataset_totals.setdefault(dataset, {"cases": 0, "complete": 0})
        ds["cases"] += 1
        ds["complete"] += not missing
        totals["cases"] += 1
        totals["complete"] += not missing
        totals["gold"] += len(context["gold_tables"])
        totals["covered"] += len(context["gold_tables"]) - len(missing)
        totals["full_tables"] += len(context["tables"])
        totals["selected_tables"] += len(linked["selected_tables"])
        totals["full_chars"] += len(context["full_schema"])
        totals["selected_chars"] += len(linked["selected_schema"])
        totals["fallback"] += linked["selection_mode"] == "full_schema_fallback"
        if keep_cases:
            case = context["case"]
            case_rows.append({
                "id": case["id"], "dataset": dataset, "db_id": case["db_id"],
                "question": case["question"], "selection_mode": linked["selection_mode"],
                "fallback_reason": linked["fallback_reason"], "cutoff_gap": linked["cutoff_gap"],
                "seed_tables": linked["seed_tables"], "selected_tables": linked["selected_tables"],
                "selected_schema": linked["selected_schema"], "ranked_tables": context["rankings"],
                "gold_tables": context["gold_tables"], "missing_gold_tables": missing,
                "all_gold_tables_covered": not missing,
            })
    result = {
        **config,
        "case_count": totals["cases"], "complete_coverage_count": totals["complete"],
        "case_level_gold_table_coverage": round(totals["complete"]/totals["cases"], 4),
        "micro_gold_table_recall": round(totals["covered"]/totals["gold"], 4),
        "fallback_count": totals["fallback"],
        "fallback_rate": round(totals["fallback"]/totals["cases"], 4),
        "average_selected_table_count": round(totals["selected_tables"]/totals["cases"], 3),
        "table_reduction_rate": round(1-totals["selected_tables"]/totals["full_tables"], 4),
        "schema_character_reduction_rate": round(1-totals["selected_chars"]/totals["full_chars"], 4),
        "coverage_by_dataset": {
            name: {"case_count": x["cases"], "complete_coverage_count": x["complete"],
                   "coverage": round(x["complete"]/x["cases"], 4)}
            for name, x in dataset_totals.items()
        },
    }
    if keep_cases:
        result["cases"] = case_rows
    return result


def main() -> None:
    contexts = load_contexts()
    candidates = []
    for small, fraction, gap, one_hop in itertools.product(
        (4, 6, 8), (0.4, 0.5, 0.6, 0.7), (0.0, 2.0, 5.0), (False, True)
    ):
        config = {
            "small_schema_threshold": small, "seed_fraction": fraction,
            "min_cutoff_gap": gap, "add_one_hop_neighbors": one_hop,
            "near_full_fraction": 0.9,
        }
        candidates.append(evaluate(contexts, config))
    qualified = [x for x in candidates if x["case_level_gold_table_coverage"] >= TARGET_COVERAGE]
    pool = qualified or candidates
    chosen = max(pool, key=lambda x: (
        x["schema_character_reduction_rate"], x["case_level_gold_table_coverage"],
        -x["fallback_rate"],
    )) if qualified else max(pool, key=lambda x: (
        x["case_level_gold_table_coverage"], x["schema_character_reduction_rate"]
    ))
    config_keys = ("small_schema_threshold", "seed_fraction", "min_cutoff_gap",
                   "add_one_hop_neighbors", "near_full_fraction")
    chosen_config = {key: chosen[key] for key in config_keys}
    detailed = evaluate(contexts, chosen_config, keep_cases=True)

    comparison = {
        "method": "dynamic lexical seeds + FK expansion + confidence fallback",
        "status": "post-hoc exploratory development after held-out failure",
        "gold_sql_used_for_per_case_selection": False,
        "gold_sql_used_for_configuration_selection": True,
        "target_complete_coverage": TARGET_COVERAGE,
        "selection_rule": "among configurations reaching target coverage, maximize schema character reduction",
        "candidate_count": len(candidates), "chosen": chosen,
        "candidates": candidates,
    }
    COMPARISON.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    validation_cases = [x for x in detailed["cases"] if x["dataset"] == "expanded_validation_150"]
    selection_report = {
        "method": comparison["method"], "configuration": chosen_config,
        "gold_sql_used_for_per_case_selection": False,
        "case_count": len(validation_cases),
        "cases": [{key: value for key, value in x.items() if key not in ("gold_tables", "missing_gold_tables", "all_gold_tables_covered", "dataset")}
                  for x in validation_cases],
    }
    audit_report = {
        "method": comparison["method"], "configuration": chosen_config,
        "important_note": "Gold tables are used for post-selection configuration audit; this 150-case set is now validation, not untouched test.",
        **{key: value for key, value in detailed.items() if key not in (*config_keys, "cases")},
        "cases": [{key: value for key, value in x.items() if key != "selected_schema"}
                  for x in detailed["cases"]],
    }
    SELECTIONS.write_text(json.dumps(selection_report, ensure_ascii=False, indent=2), encoding="utf-8")
    AUDIT.write_text(json.dumps(audit_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("动态Schema策略离线选择完成：")
    print(json.dumps(chosen, ensure_ascii=False, indent=2))
    missing = [x for x in detailed["cases"] if x["missing_gold_tables"]]
    print(f"仍有遗漏的题目：{len(missing)}")
    for x in missing:
        print(f"- {x['id']} [{x['dataset']}]: missing={x['missing_gold_tables']}, mode={x['selection_mode']}")
    print(f"配置比较：{COMPARISON.resolve()}")
    print(f"验证集选择：{SELECTIONS.resolve()}")


if __name__ == "__main__":
    main()

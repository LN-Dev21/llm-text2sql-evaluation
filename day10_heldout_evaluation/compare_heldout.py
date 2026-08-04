"""生成完整Schema与冻结词法Schema Linking的held-out配对比较。"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
FULL_RESULTS = DAY_DIR / "heldout_full_schema_results.json"
LEXICAL_RESULTS = DAY_DIR / "heldout_lexical_results.json"
FULL_CASES = DAY_DIR / "heldout_full_schema_test_suite_case_analysis.json"
LEXICAL_CASES = DAY_DIR / "heldout_lexical_test_suite_case_analysis.json"
AUDIT = DAY_DIR / "heldout_lexical_audit.json"
OUTPUT = DAY_DIR / "heldout_paired_comparison.json"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_mcnemar_p(full_only: int, lexical_only: int) -> float:
    discordant = full_only + lexical_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(full_only, lexical_only)+1))
    return min(1.0, 2*tail/(2**discordant))


def main() -> None:
    full_report, lexical_report = read(FULL_RESULTS), read(LEXICAL_RESULTS)
    full_cases_report, lexical_cases_report = read(FULL_CASES), read(LEXICAL_CASES)
    full = {x["id"]: x for x in full_cases_report["cases"]}
    lexical = {x["id"]: x for x in lexical_cases_report["cases"]}
    audit = {x["id"]: x for x in read(AUDIT)["cases"]}
    if set(full) != set(lexical) or set(full) != set(audit):
        raise RuntimeError("两组结果或审计文件的题目ID不一致。")

    transitions = Counter(
        (bool(full[i]["test_suite_pass"]), bool(lexical[i]["test_suite_pass"]))
        for i in full
    )
    full_only = transitions[(True, False)]
    lexical_only = transitions[(False, True)]
    databases = sorted({x["db_id"] for x in full.values()})
    by_database = []
    for db_id in databases:
        ids = [i for i, x in full.items() if x["db_id"] == db_id]
        by_database.append({
            "db_id": db_id, "case_count": len(ids),
            "full_schema_correct": sum(full[i]["test_suite_pass"] for i in ids),
            "lexical_correct": sum(lexical[i]["test_suite_pass"] for i in ids),
        })

    coverage_groups = []
    for covered in (True, False):
        ids = [i for i, x in audit.items() if bool(x["all_gold_tables_covered"]) == covered]
        coverage_groups.append({
            "all_gold_tables_covered": covered, "case_count": len(ids),
            "full_schema_correct": sum(full[i]["test_suite_pass"] for i in ids),
            "lexical_correct": sum(lexical[i]["test_suite_pass"] for i in ids),
        })

    fs = full_report["summary"]
    ls = lexical_report["summary"]
    comparison = {
        "experiment": "150-case internal held-out paired comparison",
        "primary_metric": "Spider Test Suite Accuracy",
        "full_schema": {
            "correct": full_cases_report["test_suite_correct_count"],
            "accuracy": full_cases_report["test_suite_accuracy"],
            "single_database_correct": full_cases_report["single_database_correct_count"],
            "single_database_false_positives": full_cases_report["single_database_false_positive_count"],
            "execution_success_count": fs["execution_success_count"],
            "total_tokens": fs["total_tokens"], "average_latency_seconds": fs["average_latency_seconds"],
        },
        "lexical_top4": {
            "correct": lexical_cases_report["test_suite_correct_count"],
            "accuracy": lexical_cases_report["test_suite_accuracy"],
            "single_database_correct": lexical_cases_report["single_database_correct_count"],
            "single_database_false_positives": lexical_cases_report["single_database_false_positive_count"],
            "execution_success_count": ls["execution_success_count"],
            "total_tokens": ls["total_tokens"], "average_latency_seconds": ls["average_latency_seconds"],
        },
        "efficiency_change": {
            "token_reduction_rate": round(1-ls["total_tokens"]/fs["total_tokens"], 4),
            "latency_change_rate": round(ls["average_latency_seconds"]/fs["average_latency_seconds"]-1, 4),
        },
        "paired_transitions": {
            "both_correct": transitions[(True, True)], "full_schema_only_correct": full_only,
            "lexical_only_correct": lexical_only, "both_wrong": transitions[(False, False)],
            "full_schema_only_ids": [i for i in full if full[i]["test_suite_pass"] and not lexical[i]["test_suite_pass"]],
            "lexical_only_ids": [i for i in full if not full[i]["test_suite_pass"] and lexical[i]["test_suite_pass"]],
        },
        "mcnemar_exact_two_sided_p": round(exact_mcnemar_p(full_only, lexical_only), 8),
        "statistical_conclusion_at_alpha_0_05": "lexical Top-4 is significantly worse than full schema",
        "by_database": by_database, "by_gold_table_coverage": coverage_groups,
        "methodological_note": "Public Spider train_others is used as an internal project held-out split, not the official hidden test set; possible model pretraining contamination remains a limitation.",
    }
    OUTPUT.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(f"比较报告：{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()

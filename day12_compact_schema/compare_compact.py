"""Compare compact-schema validation with the full-schema baseline."""

from __future__ import annotations

import json
import math
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY10_DIR = PROJECT_ROOT / "day10_heldout_evaluation"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def exact_mcnemar_p_value(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    lower_tail = sum(
        math.comb(discordant, index) for index in range(min(left_only, right_only) + 1)
    ) / (2**discordant)
    return min(1.0, 2 * lower_tail)


def main() -> None:
    full_cases = load_json(
        DAY10_DIR / "heldout_full_schema_test_suite_case_analysis.json"
    )["cases"]
    compact_cases = load_json(DAY_DIR / "compact_test_suite_case_analysis.json")["cases"]
    full_results = load_json(DAY10_DIR / "heldout_full_schema_results.json")
    compact_results = load_json(DAY_DIR / "compact_validation_results.json")

    full_by_id = {item["id"]: item for item in full_cases}
    compact_by_id = {item["id"]: item for item in compact_cases}
    if full_by_id.keys() != compact_by_id.keys():
        raise ValueError("Full-schema and compact-schema case IDs do not match.")

    both_correct: list[str] = []
    full_only: list[str] = []
    compact_only: list[str] = []
    both_wrong: list[str] = []
    by_database: dict[str, dict[str, int]] = {}

    for case_id, full in full_by_id.items():
        compact = compact_by_id[case_id]
        full_pass = bool(full["test_suite_pass"])
        compact_pass = bool(compact["test_suite_pass"])
        if full_pass and compact_pass:
            both_correct.append(case_id)
        elif full_pass:
            full_only.append(case_id)
        elif compact_pass:
            compact_only.append(case_id)
        else:
            both_wrong.append(case_id)

        db_stats = by_database.setdefault(
            full["db_id"], {"case_count": 0, "full_correct": 0, "compact_correct": 0}
        )
        db_stats["case_count"] += 1
        db_stats["full_correct"] += int(full_pass)
        db_stats["compact_correct"] += int(compact_pass)

    case_count = len(full_by_id)
    full_correct = len(both_correct) + len(full_only)
    compact_correct = len(both_correct) + len(compact_only)
    full_tokens = full_results["summary"]["total_tokens"]
    compact_tokens = compact_results["summary"]["total_tokens"]
    token_reduction = 1 - compact_tokens / full_tokens
    p_value = exact_mcnemar_p_value(len(full_only), len(compact_only))

    report = {
        "experiment": "compact complete-schema versus full-schema paired comparison",
        "case_count": case_count,
        "primary_metric": "Spider Test Suite Accuracy",
        "full_schema": {
            "correct": full_correct,
            "accuracy": round(full_correct / case_count, 4),
            "total_tokens": full_tokens,
        },
        "compact_schema": {
            "correct": compact_correct,
            "accuracy": round(compact_correct / case_count, 4),
            "total_tokens": compact_tokens,
        },
        "efficiency_change": {
            "token_reduction_rate": round(token_reduction, 4),
            "token_reduction_count": full_tokens - compact_tokens,
        },
        "paired_transitions": {
            "both_correct": len(both_correct),
            "full_schema_only_correct": len(full_only),
            "compact_schema_only_correct": len(compact_only),
            "both_wrong": len(both_wrong),
            "full_schema_only_ids": full_only,
            "compact_schema_only_ids": compact_only,
        },
        "mcnemar_exact_two_sided_p": round(p_value, 8),
        "statistical_conclusion_at_alpha_0_05": (
            "no statistically significant difference"
            if p_value >= 0.05
            else "statistically significant difference"
        ),
        "predeclared_criteria": {
            "minimum_test_suite_correct": 43,
            "minimum_token_reduction_rate": 0.25,
            "accuracy_requirement_met": compact_correct >= 43,
            "token_requirement_met": token_reduction >= 0.25,
            "overall_requirement_met": (
                compact_correct >= 43 and token_reduction >= 0.25
            ),
        },
        "by_database": [
            {"db_id": db_id, **stats} for db_id, stats in sorted(by_database.items())
        ],
        "methodological_note": (
            "Four API-timeout cases with empty outputs were retried once by resume; "
            "all non-empty model outputs were kept unchanged."
        ),
    }
    output = DAY_DIR / "compact_paired_comparison.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告：{output.resolve()}")


if __name__ == "__main__":
    main()

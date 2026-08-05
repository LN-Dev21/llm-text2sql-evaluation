"""Prepare frozen Day 13 outputs for the official BIRD Mini-Dev evaluator."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DATA_ROOT = PROJECT_ROOT / "data" / "bird_mini_dev" / "minidev" / "MINIDEV"
SOURCE_PATH = DATA_ROOT / "mini_dev_sqlite.json"
FULL_RESULTS_PATH = DAY_DIR / "bird_full_schema_final_results.json"
COMPACT_RESULTS_PATH = DAY_DIR / "bird_compact_schema_final_results.json"
OFFICIAL_DIR = DAY_DIR / "official_evaluation"


def load_results(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload["results"]
    if len(results) != 500:
        raise RuntimeError(f"Expected 500 results in {path.name}, found {len(results)}")
    if len({item["id"] for item in results}) != len(results):
        raise RuntimeError(f"Duplicate result IDs in {path.name}")
    return results


def exact_mcnemar_p(full_only: int, compact_only: int) -> float:
    discordant = full_only + compact_only
    if discordant == 0:
        return 1.0
    lower = min(full_only, compact_only)
    tail = sum(math.comb(discordant, k) for k in range(lower + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def build_predictions(
    source: list[dict[str, Any]], results: list[dict[str, Any]]
) -> dict[str, str]:
    by_question_id = {item["question_id"]: item for item in results}
    if set(by_question_id) != {item["question_id"] for item in source}:
        raise RuntimeError("Result question IDs do not match the official Mini-Dev source")

    predictions: dict[str, str] = {}
    for index, case in enumerate(source):
        result = by_question_id[case["question_id"]]
        if result["db_id"] != case["db_id"]:
            raise RuntimeError(f"Database mismatch for question {case['question_id']}")
        sql = (result.get("generated_sql") or "SELECT FROM").strip()
        predictions[str(index)] = (
            f"{sql}\t----- bird -----\t{case['db_id']}"
        )
    return predictions


def paired_report(
    full: list[dict[str, Any]], compact: list[dict[str, Any]]
) -> dict[str, Any]:
    full_by_id = {item["id"]: item for item in full}
    compact_by_id = {item["id"]: item for item in compact}
    if set(full_by_id) != set(compact_by_id):
        raise RuntimeError("Full and compact result IDs differ")

    ids = list(full_by_id)
    full_correct = lambda item: bool(item["preliminary_is_correct"])
    compact_correct = full_correct
    both_correct = sum(
        full_correct(full_by_id[item_id]) and compact_correct(compact_by_id[item_id])
        for item_id in ids
    )
    full_only = sum(
        full_correct(full_by_id[item_id]) and not compact_correct(compact_by_id[item_id])
        for item_id in ids
    )
    compact_only = sum(
        not full_correct(full_by_id[item_id]) and compact_correct(compact_by_id[item_id])
        for item_id in ids
    )
    both_wrong = len(ids) - both_correct - full_only - compact_only

    full_tokens = sum(item["total_tokens"] for item in full)
    compact_tokens = sum(item["total_tokens"] for item in compact)
    full_schema_chars = sum(item["schema_character_count"] for item in full)
    compact_schema_chars = sum(item["schema_character_count"] for item in compact)

    return {
        "dataset": "BIRD Mini-Dev SQLite",
        "case_count": len(ids),
        "metric_status": "local preliminary comparison; official EX follows",
        "full_schema": {
            "execution_success_count": sum(item["execution_success"] for item in full),
            "preliminary_correct_count": sum(full_correct(item) for item in full),
            "total_tokens": full_tokens,
            "schema_character_total": full_schema_chars,
        },
        "compact_schema": {
            "execution_success_count": sum(item["execution_success"] for item in compact),
            "preliminary_correct_count": sum(compact_correct(item) for item in compact),
            "total_tokens": compact_tokens,
            "schema_character_total": compact_schema_chars,
        },
        "paired_correctness": {
            "both_correct": both_correct,
            "full_only_correct": full_only,
            "compact_only_correct": compact_only,
            "both_wrong": both_wrong,
            "discordant_count": full_only + compact_only,
            "mcnemar_exact_two_sided_p": exact_mcnemar_p(full_only, compact_only),
        },
        "efficiency": {
            "token_reduction_count": full_tokens - compact_tokens,
            "token_reduction_rate": round(1 - compact_tokens / full_tokens, 6),
            "schema_character_reduction_rate": round(
                1 - compact_schema_chars / full_schema_chars, 6
            ),
        },
    }


def main() -> None:
    OFFICIAL_DIR.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    full = load_results(FULL_RESULTS_PATH)
    compact = load_results(COMPACT_RESULTS_PATH)

    (OFFICIAL_DIR / "full_predictions.json").write_text(
        json.dumps(build_predictions(source, full), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OFFICIAL_DIR / "compact_predictions.json").write_text(
        json.dumps(build_predictions(source, compact), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (OFFICIAL_DIR / "difficulty.jsonl").open("w", encoding="utf-8") as handle:
        for case in source:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    # The distributed SQLite gold file contains a few malformed separators.
    # Reconstruct the evaluator's documented ``SQL<TAB>db_id`` representation
    # directly from the same official JSON records without changing any SQL.
    (OFFICIAL_DIR / "official_gold.sql").write_text(
        "\n".join(f"{case['SQL']}\t{case['db_id']}" for case in source) + "\n",
        encoding="utf-8",
    )

    report = paired_report(full, compact)
    (DAY_DIR / "bird_paired_comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Official evaluator inputs saved to: {OFFICIAL_DIR}")


if __name__ == "__main__":
    main()

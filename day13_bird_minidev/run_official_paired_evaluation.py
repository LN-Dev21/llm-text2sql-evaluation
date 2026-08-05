"""Run the official BIRD EX semantics and save paired per-case results."""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
OFFICIAL_DIR = DAY_DIR / "official_evaluation"
DATA_ROOT = PROJECT_ROOT / "data" / "bird_mini_dev" / "minidev" / "MINIDEV"
SOURCE_PATH = DATA_ROOT / "mini_dev_sqlite.json"
DATABASE_ROOT = DATA_ROOT / "dev_databases"
GOLD_PATH = OFFICIAL_DIR / "official_gold.sql"
FULL_PREDICTIONS = OFFICIAL_DIR / "full_predictions.json"
COMPACT_PREDICTIONS = OFFICIAL_DIR / "compact_predictions.json"
OUTPUT_PATH = DAY_DIR / "bird_official_paired_comparison.json"

sys.path.insert(0, str(OFFICIAL_DIR))
from evaluation_ex import execute_model  # noqa: E402
from evaluation_utils import package_sqls, sort_results  # noqa: E402


def evaluate(prediction_path: Path, workers: int, timeout: float) -> list[dict[str, Any]]:
    predictions, _ = package_sqls(str(prediction_path), str(DATABASE_ROOT) + "/", mode="pred")
    gold, db_paths = package_sqls(str(GOLD_PATH), str(DATABASE_ROOT) + "/", mode="gt")
    if not (len(predictions) == len(gold) == len(db_paths) == 500):
        raise RuntimeError("Official evaluator inputs must contain exactly 500 aligned cases")
    tasks = [
        (predictions[index], gold[index], db_paths[index], index, timeout, "SQLite")
        for index in range(len(gold))
    ]
    with mp.Pool(processes=workers) as pool:
        return sort_results(pool.starmap(execute_model, tasks))


def exact_mcnemar_p(full_only: int, compact_only: int) -> float:
    discordant = full_only + compact_only
    if discordant == 0:
        return 1.0
    lower = min(full_only, compact_only)
    tail = sum(math.comb(discordant, k) for k in range(lower + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def accuracy_by_difficulty(
    source: list[dict[str, Any]], results: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for case, result in zip(source, results, strict=True):
        grouped[case["difficulty"]].append(int(result["res"]))
    return {
        difficulty: {
            "count": len(values),
            "correct": sum(values),
            "accuracy": round(sum(values) / len(values), 6),
        }
        for difficulty, values in sorted(grouped.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.workers <= 0 or args.timeout <= 0:
        raise SystemExit("--workers and --timeout must be positive")

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    full = evaluate(FULL_PREDICTIONS, args.workers, args.timeout)
    compact = evaluate(COMPACT_PREDICTIONS, args.workers, args.timeout)
    full_flags = [int(item["res"]) for item in full]
    compact_flags = [int(item["res"]) for item in compact]

    both_correct = sum(a == 1 and b == 1 for a, b in zip(full_flags, compact_flags))
    full_only = sum(a == 1 and b == 0 for a, b in zip(full_flags, compact_flags))
    compact_only = sum(a == 0 and b == 1 for a, b in zip(full_flags, compact_flags))
    both_wrong = len(source) - both_correct - full_only - compact_only

    report = {
        "dataset": "BIRD Mini-Dev SQLite",
        "evaluator_source": "https://github.com/bird-bench/mini_dev/tree/main/evaluation",
        "metric": "official Execution Accuracy semantics",
        "sql_dialect": "SQLite",
        "timeout_seconds": args.timeout,
        "case_count": len(source),
        "full_schema": {
            "correct": sum(full_flags),
            "accuracy": round(sum(full_flags) / len(full_flags), 6),
            "by_difficulty": accuracy_by_difficulty(source, full),
        },
        "compact_schema": {
            "correct": sum(compact_flags),
            "accuracy": round(sum(compact_flags) / len(compact_flags), 6),
            "by_difficulty": accuracy_by_difficulty(source, compact),
        },
        "paired_correctness": {
            "both_correct": both_correct,
            "full_only_correct": full_only,
            "compact_only_correct": compact_only,
            "both_wrong": both_wrong,
            "discordant_count": full_only + compact_only,
            "mcnemar_exact_two_sided_p": exact_mcnemar_p(full_only, compact_only),
        },
        "per_case": [
            {
                "question_id": case["question_id"],
                "db_id": case["db_id"],
                "difficulty": case["difficulty"],
                "full_correct": bool(full_result["res"]),
                "compact_correct": bool(compact_result["res"]),
            }
            for case, full_result, compact_result in zip(source, full, compact, strict=True)
        ],
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in report.items() if key != "per_case"}, ensure_ascii=False, indent=2))
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    mp.freeze_support()
    main()

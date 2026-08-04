"""分析 Spider 子集错误，并计算允许输出列置换的单数据库执行结果。"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Iterable


DAY_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = DAY_DIR / "spider_baseline_results.json"
DEFAULT_OUTPUT = DAY_DIR / "error_analysis.json"


def normalize_value(value: Any) -> Any:
    return round(value, 6) if isinstance(value, float) else value


def normalize_rows(rows: list[list[Any]]) -> list[tuple[Any, ...]]:
    return [tuple(normalize_value(value) for value in row) for row in rows]


def row_signature(row: tuple[Any, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((type(value).__name__, repr(value)) for value in row))


def candidate_permutations(
    gold: list[tuple[Any, ...]], predicted: list[tuple[Any, ...]]
) -> Iterable[tuple[int, ...]]:
    column_count = len(gold[0])
    if column_count <= 3:
        return itertools.permutations(range(column_count))

    gold_columns = [{row[index] for row in gold} for index in range(column_count)]
    predicted_columns = [
        {row[index] for row in predicted} for index in range(column_count)
    ]
    allowed = [
        [pred_index for pred_index, values in enumerate(predicted_columns) if values == gold_values]
        for gold_values in gold_columns
    ]
    return (
        permutation
        for permutation in itertools.product(*allowed)
        if len(set(permutation)) == column_count
    )


def permutation_aware_equal(
    gold_rows: list[list[Any]],
    predicted_rows: list[list[Any]],
    order_matters: bool,
) -> bool:
    gold = normalize_rows(gold_rows)
    predicted = normalize_rows(predicted_rows)
    if not gold and not predicted:
        return True
    if len(gold) != len(predicted) or not gold or not predicted:
        return False
    if len(gold[0]) != len(predicted[0]):
        return False

    gold_signatures = [row_signature(row) for row in gold]
    predicted_signatures = [row_signature(row) for row in predicted]
    if order_matters:
        if gold_signatures != predicted_signatures:
            return False
    elif sorted(gold_signatures) != sorted(predicted_signatures):
        return False

    for permutation in candidate_permutations(gold, predicted):
        permuted = [tuple(row[index] for index in permutation) for row in predicted]
        if order_matters:
            if gold == permuted:
                return True
        elif sorted(gold, key=repr) == sorted(permuted, key=repr):
            return True
    return False


def classify(result: dict[str, Any], compatible: bool) -> str:
    if not result["execution_success"]:
        return "execution_error"
    if result["preliminary_is_correct"]:
        return "strict_result_match"
    if compatible:
        return "column_permutation_equivalent"
    if len(result["predicted_rows"]) != len(result["gold_rows"]):
        return "row_count_mismatch"
    if result["predicted_rows"] and result["gold_rows"]:
        if len(result["predicted_rows"][0]) != len(result["gold_rows"][0]):
            return "column_count_mismatch"
    return "result_value_mismatch"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = report["results"]
    analyses: list[dict[str, Any]] = []
    strict_correct = 0
    compatible_correct = 0

    for result in results:
        strict = bool(result["preliminary_is_correct"])
        compatible = bool(
            result["execution_success"]
            and permutation_aware_equal(
                result["gold_rows"],
                result["predicted_rows"],
                result["gold_order_matters"],
            )
        )
        strict_correct += strict
        compatible_correct += compatible
        category = classify(result, compatible)
        analyses.append(
            {
                "id": result["id"],
                "db_id": result["db_id"],
                "question": result["question"],
                "generated_sql": result["generated_sql"],
                "gold_sql": result["gold_sql"],
                "strict_result_match": strict,
                "column_permutation_aware_match": compatible,
                "category": category,
            }
        )

    count = len(results)
    output = {
        "input_file": str(args.input.resolve()),
        "case_count": count,
        "strict_correct_count": strict_correct,
        "strict_accuracy": round(strict_correct / count, 4) if count else 0.0,
        "column_permutation_aware_correct_count": compatible_correct,
        "column_permutation_aware_single_database_accuracy": round(
            compatible_correct / count, 4
        )
        if count
        else 0.0,
        "important_note": (
            "Column-permutation-aware comparison follows a key behavior of the official "
            "execution evaluator, but this still runs only the original SQLite database "
            "and is not official Test Suite Accuracy."
        ),
        "cases": analyses,
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"严格逐列结果：{strict_correct}/{count} = {output['strict_accuracy']:.1%}")
    print(
        "允许等价列置换："
        f"{compatible_correct}/{count} = "
        f"{output['column_permutation_aware_single_database_accuracy']:.1%}"
    )
    print("\n非严格匹配题目：")
    for item in analyses:
        if not item["strict_result_match"]:
            print(f"- {item['id']}: {item['category']}")
    print(f"分析结果：{args.output.resolve()}")


if __name__ == "__main__":
    main()


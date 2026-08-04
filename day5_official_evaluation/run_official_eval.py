"""把 Day4 结果转换成 Spider 官方格式并调用官方执行评测器。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DEFAULT_RESULTS = PROJECT_ROOT / "day4_spider_subset" / "spider_baseline_results.json"
DEFAULT_EVALUATOR = (
    PROJECT_ROOT / "third_party" / "test-suite-sql-eval" / "evaluation.py"
)
DEFAULT_NLTK_DATA = PROJECT_ROOT / "third_party" / "nltk_data"
DEFAULT_DATABASE_ROOT = PROJECT_ROOT / "data" / "spider_data" / "database"
DEFAULT_GOLD = DAY_DIR / "official_gold.txt"
DEFAULT_PREDICTIONS = DAY_DIR / "official_predictions.txt"
DEFAULT_OUTPUT = DAY_DIR / "official_single_db_output.txt"
DEFAULT_METADATA = DAY_DIR / "official_eval_metadata.json"


def load_completed_results(path: Path) -> list[dict[str, Any]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    results = report.get("results", [])
    expected = report.get("summary", {}).get("dataset_size")
    if not results:
        raise ValueError("结果文件中没有模型预测。")
    if expected is not None and len(results) != expected:
        raise ValueError(f"实验尚未完成：预期 {expected} 条，实际 {len(results)} 条。")
    for item in results:
        if not item.get("generated_sql"):
            raise ValueError(f"{item.get('id')} 没有生成 SQL。")
    return results


def write_official_inputs(
    results: list[dict[str, Any]], gold_path: Path, prediction_path: Path
) -> None:
    gold_lines = [f"{item['gold_sql']}\t{item['db_id']}" for item in results]
    prediction_lines = [item["generated_sql"] for item in results]
    gold_path.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")
    prediction_path.write_text(
        "\n".join(prediction_lines) + "\n", encoding="utf-8"
    )


def inspect_database_instances(
    results: list[dict[str, Any]], database_root: Path
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for db_id in sorted({item["db_id"] for item in results}):
        folder = database_root / db_id
        if not folder.is_dir():
            raise FileNotFoundError(f"找不到评测数据库目录：{folder}")
        count = len(list(folder.glob("*.sqlite")))
        if count == 0:
            raise FileNotFoundError(f"{folder} 中没有 SQLite 文件。")
        counts[db_id] = count
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--evaluator", type=Path, default=DEFAULT_EVALUATOR)
    parser.add_argument("--database-root", type=Path, default=DEFAULT_DATABASE_ROOT)
    parser.add_argument("--nltk-data", type=Path, default=DEFAULT_NLTK_DATA)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument(
        "--keep-distinct",
        action="store_true",
        help="保留 DISTINCT；官方默认会在执行比较前移除 DISTINCT。",
    )
    args = parser.parse_args()

    for path, label in (
        (args.results, "Day4 结果"),
        (args.evaluator, "官方 evaluation.py"),
    ):
        if not path.is_file():
            raise SystemExit(f"找不到{label}：{path}")
    if not args.database_root.is_dir():
        raise SystemExit(f"找不到数据库根目录：{args.database_root}")

    results = load_completed_results(args.results)
    args.gold.parent.mkdir(parents=True, exist_ok=True)
    write_official_inputs(results, args.gold, args.predictions)
    instance_counts = inspect_database_instances(results, args.database_root)
    is_test_suite = any(count > 1 for count in instance_counts.values())

    command = [
        sys.executable,
        str(args.evaluator.resolve()),
        "--gold",
        str(args.gold.resolve()),
        "--pred",
        str(args.predictions.resolve()),
        "--db",
        str(args.database_root.resolve()),
        "--etype",
        "exec",
    ]
    if args.keep_distinct:
        command.append("--keep_distinct")
    child_environment = os.environ.copy()
    child_environment["NLTK_DATA"] = str(args.nltk_data.resolve())
    completed = subprocess.run(
        command,
        cwd=args.evaluator.parent,
        env=child_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined_output = completed.stdout
    if completed.stderr:
        combined_output += "\n[stderr]\n" + completed.stderr
    args.output.write_text(combined_output, encoding="utf-8")

    metadata = {
        "evaluator_repository": "https://github.com/taoyds/test-suite-sql-eval",
        "evaluator_file": str(args.evaluator.resolve()),
        "database_root": str(args.database_root.resolve()),
        "database_instance_counts": instance_counts,
        "uses_multiple_test_databases": is_test_suite,
        "keep_distinct": args.keep_distinct,
        "metric_label": (
            "Spider Test Suite Accuracy"
            if is_test_suite
            else "official evaluator on original single databases (not Test Suite Accuracy)"
        ),
        "case_count": len(results),
        "gold_file": str(args.gold.resolve()),
        "prediction_file": str(args.predictions.resolve()),
        "output_file": str(args.output.resolve()),
        "return_code": completed.returncode,
    }
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    console_encoding = sys.stdout.encoding or "utf-8"
    console_output = combined_output.rstrip().encode(
        console_encoding, errors="replace"
    ).decode(console_encoding)
    print(console_output)
    print("\n评测类型：" + metadata["metric_label"])
    print(f"保留 DISTINCT：{args.keep_distinct}")
    print("数据库实例数：" + json.dumps(instance_counts, ensure_ascii=False))
    print(f"输出文件：{args.output.resolve()}")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()

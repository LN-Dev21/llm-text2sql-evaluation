"""逐题比较官方单数据库执行结果与Test Suite Accuracy。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
EVALUATOR_ROOT = PROJECT_ROOT / "third_party" / "test-suite-sql-eval"
sys.path.insert(0, str(EVALUATOR_ROOT))

from exec_eval import eval_exec_match  # noqa: E402


DEFAULT_RESULTS = PROJECT_ROOT / "day4_spider_subset" / "spider_baseline_results.json"
DEFAULT_SINGLE_DB_ROOT = PROJECT_ROOT / "data" / "spider_data" / "database"
DEFAULT_TEST_SUITE_ROOT = (
    PROJECT_ROOT / "data" / "test_suite_databases" / "database"
)
DEFAULT_OUTPUT = DAY_DIR / "test_suite_case_analysis.json"


def representative_database(database_root: Path, db_id: str) -> Path:
    folder = database_root / db_id
    preferred = folder / f"{db_id}.sqlite"
    if preferred.is_file():
        return preferred
    candidates = sorted(folder.glob("*.sqlite"))
    if not candidates:
        raise FileNotFoundError(f"{folder} 中没有 SQLite 文件")
    return candidates[0]


def official_exec_match(
    db_path: Path, predicted_sql: str, gold_sql: str, keep_distinct: bool
) -> bool:
    return bool(
        eval_exec_match(
            db=str(db_path),
            p_str=predicted_sql,
            g_str=gold_sql,
            plug_value=False,
            keep_distinct=keep_distinct,
            progress_bar_for_each_datapoint=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--single-db-root", type=Path, default=DEFAULT_SINGLE_DB_ROOT)
    parser.add_argument("--test-suite-root", type=Path, default=DEFAULT_TEST_SUITE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--keep-distinct", action="store_true")
    args = parser.parse_args()

    report = json.loads(args.results.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = report["results"]
    cases: list[dict[str, Any]] = []

    for index, item in enumerate(results, start=1):
        single_db = representative_database(args.single_db_root, item["db_id"])
        suite_db = representative_database(args.test_suite_root, item["db_id"])
        single_pass = official_exec_match(
            single_db,
            item["generated_sql"],
            item["gold_sql"],
            args.keep_distinct,
        )
        suite_pass = official_exec_match(
            suite_db,
            item["generated_sql"],
            item["gold_sql"],
            args.keep_distinct,
        )
        cases.append(
            {
                "id": item["id"],
                "db_id": item["db_id"],
                "question": item["question"],
                "generated_sql": item["generated_sql"],
                "gold_sql": item["gold_sql"],
                "single_database_pass": single_pass,
                "test_suite_pass": suite_pass,
                "single_database_false_positive": single_pass and not suite_pass,
            }
        )
        print(
            f"[{index}/{len(results)}] {item['id']}: "
            f"single={'PASS' if single_pass else 'FAIL'}, "
            f"suite={'PASS' if suite_pass else 'FAIL'}"
        )

    single_count = sum(item["single_database_pass"] for item in cases)
    suite_count = sum(item["test_suite_pass"] for item in cases)
    false_positive_count = sum(item["single_database_false_positive"] for item in cases)
    output = {
        "case_count": len(cases),
        "keep_distinct": args.keep_distinct,
        "single_database_correct_count": single_count,
        "single_database_execution_accuracy": round(single_count / len(cases), 4),
        "test_suite_correct_count": suite_count,
        "test_suite_accuracy": round(suite_count / len(cases), 4),
        "single_database_false_positive_count": false_positive_count,
        "cases": cases,
    }
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n逐题汇总：")
    print(f"单数据库：{single_count}/{len(cases)}")
    print(f"Test Suite：{suite_count}/{len(cases)}")
    print(f"被增强数据库揭示的假阳性：{false_positive_count}")
    print("Test Suite 失败题：")
    for item in cases:
        if not item["test_suite_pass"]:
            marker = "（原始数据库曾通过）" if item["single_database_pass"] else ""
            print(f"- {item['id']} {marker}")
    print(f"报告：{args.output.resolve()}")


if __name__ == "__main__":
    main()


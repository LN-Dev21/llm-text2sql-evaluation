"""离线生成第一道题的反馈 Prompt，供人工检查，不调用 API。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY4_DIR = PROJECT_ROOT / "day4_spider_subset"
sys.path.insert(0, str(DAY4_DIR))

from inspect_spider import database_path  # noqa: E402
from run_spider_baseline import execute_readonly  # noqa: E402
from feedback_prompt import build_feedback_prompt  # noqa: E402


SUBSET = PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
SELECTIONS = PROJECT_ROOT / "day7_lexical_schema_linking" / "lexical_schema_selections.json"
INITIAL_RESULTS = PROJECT_ROOT / "day7_lexical_schema_linking" / "lexical_schema_results.json"
SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
OUTPUT = DAY_DIR / "feedback_prompt_example.txt"


def main() -> None:
    subset = json.loads(SUBSET.read_text(encoding="utf-8"))
    selections = json.loads(SELECTIONS.read_text(encoding="utf-8"))
    initial_report = json.loads(INITIAL_RESULTS.read_text(encoding="utf-8"))
    case = subset["cases"][0]
    selection = {item["id"]: item for item in selections["cases"]}[case["id"]]
    initial = {item["id"]: item for item in initial_report["results"]}[case["id"]]
    db_path = database_path(SPIDER_ROOT, case["db_id"])
    execution = execute_readonly(db_path, initial["generated_sql"])
    prompt = build_feedback_prompt(
        case["question"], selection["selected_schema"],
        initial["generated_sql"], execution,
    )
    OUTPUT.write_text(prompt, encoding="utf-8")
    print(f"题目：{case['id']}")
    print(f"初始执行成功：{execution['success']}")
    print(f"Prompt字符数：{len(prompt)}")
    print("Prompt输入来源：question + selected_schema + initial_sql + initial_execution")
    print("Prompt构造函数不接收gold SQL或gold执行结果。")
    print(f"示例Prompt：{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()

"""复用 Exp2 首轮 SQL，运行一次执行结果反馈自校正。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from zai import ZhipuAiClient


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY4_DIR = PROJECT_ROOT / "day4_spider_subset"
sys.path.insert(0, str(DAY4_DIR))

from inspect_spider import DEFAULT_SPIDER_ROOT, database_path  # noqa: E402
from run_spider_baseline import (  # noqa: E402
    clean_sql,
    execute_readonly,
    preliminary_match,
)
from feedback_prompt import build_feedback_prompt, execution_feedback  # noqa: E402


DEFAULT_SUBSET = PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
DEFAULT_SELECTIONS = PROJECT_ROOT / "day7_lexical_schema_linking" / "lexical_schema_selections.json"
DEFAULT_INITIAL_RESULTS = PROJECT_ROOT / "day7_lexical_schema_linking" / "lexical_schema_results.json"
DEFAULT_OUTPUT = DAY_DIR / "execution_feedback_results.json"


def normalize_sql_text(sql: str) -> str:
    return " ".join(sql.strip().rstrip(";").split()).lower()


def summarize(results: list[dict[str, Any]], dataset_size: int) -> dict[str, Any]:
    completed = len(results)
    successful = sum(bool(item["execution_success"]) for item in results)
    correct = sum(bool(item["preliminary_is_correct"]) for item in results)
    changed = sum(bool(item["sql_changed"]) for item in results)
    tokens = sum(int(item.get("total_tokens") or 0) for item in results)
    latency = sum(float(item.get("latency_seconds") or 0) for item in results)
    return {
        "dataset_size": dataset_size,
        "completed": completed,
        "initial_predictions_reused": True,
        "feedback_call_count": completed,
        "sql_changed_count": changed,
        "final_execution_success_count": successful,
        "final_execution_success_rate": round(successful/completed, 4) if completed else 0.0,
        "final_preliminary_correct_count": correct,
        "final_preliminary_execution_accuracy": round(correct/completed, 4) if completed else 0.0,
        "feedback_total_tokens": tokens,
        "average_feedback_latency_seconds": round(latency/completed, 3) if completed else 0.0,
    }


def save_report(
    path: Path, model: str, spider_root: Path, results: list[dict[str, Any]], dataset_size: int
) -> None:
    report = {
        "experiment": "Exp4 lexical schema linking plus one-pass execution-result feedback",
        "model": model,
        "spider_root": str(spider_root.resolve()),
        "initial_results": str(DEFAULT_INITIAL_RESULTS.resolve()),
        "schema_selection_file": str(DEFAULT_SELECTIONS.resolve()),
        "initial_predictions_reused": True,
        "feedback_policy": "all cases receive exactly one semantic review call",
        "gold_sql_sent_to_model": False,
        "gold_results_sent_to_model": False,
        "metric_note": "Local row comparison only; official Test Suite evaluation is required.",
        "results": results,
        "summary": summarize(results, dataset_size),
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider-root", type=Path, default=DEFAULT_SPIDER_ROOT)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--selections", type=Path, default=DEFAULT_SELECTIONS)
    parser.add_argument("--initial-results", type=Path, default=DEFAULT_INITIAL_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--api-timeout", type=float, default=30.0)
    parser.add_argument("--api-max-retries", type=int, default=1)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit必须是正整数。")

    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit("未检测到ZAI_API_KEY，请先在当前PowerShell窗口安全设置。")
    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    client = ZhipuAiClient(api_key=api_key, timeout=args.api_timeout, max_retries=args.api_max_retries)

    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    all_cases = subset["cases"]
    cases = all_cases[:args.limit] if args.limit else all_cases
    selections_report = json.loads(args.selections.read_text(encoding="utf-8"))
    selections = {item["id"]: item for item in selections_report["cases"]}
    initial_report = json.loads(args.initial_results.read_text(encoding="utf-8"))
    initial_results = {item["id"]: item for item in initial_report["results"]}
    for case in cases:
        if case["id"] not in selections or case["id"] not in initial_results:
            raise SystemExit(f"缺少题目{case['id']}的Schema选择或Exp2初始结果。")

    results_by_id: dict[str, dict[str, Any]] = {}
    if args.resume and args.output.is_file():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        results_by_id = {item["id"]: item for item in existing.get("results", [])}
        print(f"续跑模式：已读取{len(results_by_id)}条已有结果。")
    print(f"API设置：timeout={args.api_timeout:g}s, max_retries={args.api_max_retries}")
    print("首轮SQL来源：复用Exp2；反馈策略：每题恰好一次语义复核。")

    spider_root = args.spider_root.resolve()
    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        if args.resume and case_id in results_by_id and results_by_id[case_id].get("generated_sql"):
            print(f"[{index}/{len(cases)}] {case_id}: 已完成，跳过API。")
            continue
        initial = initial_results[case_id]
        initial_sql = initial["generated_sql"]
        schema = selections[case_id]["selected_schema"]
        db_path = database_path(spider_root, case["db_id"])
        initial_execution = execute_readonly(db_path, initial_sql)
        prompt = build_feedback_prompt(case["question"], schema, initial_sql, initial_execution)

        print(f"[{index}/{len(cases)}] {case_id} [{case['db_id']}]: 调用{model}自校正...")
        started = time.perf_counter()
        final_sql, call_error, finish_reason = "", None, None
        prompt_tokens = completion_tokens = total_tokens = None
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "disabled"}, temperature=0.0, max_tokens=512,
                timeout=args.api_timeout,
            )
            choice = response.choices[0]
            final_sql = clean_sql(choice.message.content)
            finish_reason = choice.finish_reason
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if not final_sql:
                call_error = "API返回内容为空。"
        except Exception as exc:
            call_error = f"{type(exc).__name__}: {exc}"
        latency = round(time.perf_counter()-started, 3)
        final_execution = execute_readonly(db_path, final_sql) if final_sql else {
            "success": False, "columns": [], "rows": [], "error": call_error
        }
        gold = execute_readonly(db_path, case["gold_sql"])
        if not gold["success"]:
            raise RuntimeError(f"{case_id}标准SQL执行失败：{gold['error']}")
        is_correct = bool(final_execution["success"] and preliminary_match(
            final_execution["rows"], gold["rows"], case["gold_order_matters"]
        ))
        result = {
            "id": case_id, "source_index": case["source_index"], "db_id": case["db_id"],
            "question": case["question"], "selected_tables": selections[case_id]["selected_tables"],
            "schema_character_count": len(schema), "initial_sql": initial_sql,
            "initial_execution_feedback": execution_feedback(initial_execution),
            "feedback_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "feedback_prompt_character_count": len(prompt), "generated_sql": final_sql,
            "sql_changed": normalize_sql_text(initial_sql) != normalize_sql_text(final_sql),
            "gold_sql": case["gold_sql"], "gold_order_matters": case["gold_order_matters"],
            "execution_success": bool(final_execution["success"]),
            "preliminary_is_correct": is_correct,
            "predicted_columns": final_execution["columns"], "predicted_rows": final_execution["rows"],
            "gold_columns": gold["columns"], "gold_rows": gold["rows"],
            "error": call_error or final_execution["error"], "latency_seconds": latency,
            "finish_reason": finish_reason, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "total_tokens": total_tokens,
        }
        results_by_id[case_id] = result
        ordered = [results_by_id[item["id"]] for item in all_cases if item["id"] in results_by_id]
        save_report(args.output, model, spider_root, ordered, len(all_cases))
        print(f"[{index}/{len(cases)}] {case_id}: {'CORRECT' if is_correct else 'WRONG'}, "
              f"changed={result['sql_changed']}, execution_success={final_execution['success']}, latency={latency}s")

    ordered = [results_by_id[item["id"]] for item in all_cases if item["id"] in results_by_id]
    print("\nExp4执行结果反馈汇总（非官方指标）：")
    print(json.dumps(summarize(ordered, len(all_cases)), ensure_ascii=False, indent=2))
    print(f"结果已保存：{args.output.resolve()}")


if __name__ == "__main__":
    main()

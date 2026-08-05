"""Run frozen full/compact-schema experiments on BIRD Mini-Dev SQLite."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from zai import ZhipuAiClient

DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DATA_ROOT = PROJECT_ROOT / "data" / "bird_mini_dev" / "minidev" / "MINIDEV"
SOURCE = DATA_ROOT / "mini_dev_sqlite.json"
DATABASE_ROOT = DATA_ROOT / "dev_databases"

sys.path.insert(0, str(PROJECT_ROOT / "day2_auto_schema"))
sys.path.insert(0, str(PROJECT_ROOT / "day4_spider_subset"))
sys.path.insert(0, str(PROJECT_ROOT / "day12_compact_schema"))
from extract_schema import extract_schema  # noqa: E402
from run_spider_baseline import (  # noqa: E402
    clean_sql, execute_readonly, preliminary_match, summarize,
)
from compact_schema import build_compact_schema  # noqa: E402


def configure_windows_console() -> None:
    """Match Python output encoding to the active Windows console code page."""
    if sys.platform != "win32" or not sys.stdout.isatty():
        return
    try:
        code_page = ctypes.windll.kernel32.GetConsoleOutputCP()
        if code_page:
            sys.stdout.reconfigure(encoding=f"cp{code_page}")
    except (AttributeError, OSError, ValueError):
        pass


def database_path(db_id: str) -> Path:
    return DATABASE_ROOT / db_id / f"{db_id}.sqlite"


def build_prompt(schema: str, question: str, evidence: str) -> str:
    return f"""You are a Text-to-SQL assistant. Convert the question into exactly one executable SQLite query.

Requirements:
1. Output SQL only, without explanation or Markdown fences.
2. Use only tables and columns present in the schema.
3. Generate a read-only SELECT or WITH query; never modify the database.
4. Use the supplied evidence when it defines domain terms, values, or calculations.

Schema:
{schema}

Evidence:
{evidence.strip() or '(none)'}

Question:
{question}
"""


def load_cases() -> list[dict[str, Any]]:
    if not SOURCE.is_file():
        raise SystemExit(f"找不到 BIRD Mini-Dev：{SOURCE}")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    return [{
        "id": f"bird_mini_{item['question_id']}",
        "question_id": item["question_id"],
        "db_id": item["db_id"],
        "question": item["question"],
        "evidence": item.get("evidence") or "",
        "gold_sql": item["SQL"],
        "difficulty": item["difficulty"],
        "gold_order_matters": "order by" in item["SQL"].lower(),
    } for item in source]


def save_report(
    output: Path,
    model: str,
    schema_mode: str,
    results: list[dict[str, Any]],
    dataset_size: int,
) -> None:
    report = {
        "experiment": f"BIRD Mini-Dev frozen {schema_mode}-schema validation",
        "dataset": "BIRD Mini-Dev SQLite (500 cases, 11 databases)",
        "source": "https://github.com/bird-bench/mini_dev",
        "model": model,
        "schema_mode": schema_mode,
        "official_evidence_provided": True,
        "gold_sql_sent_to_model": False,
        "metric_note": (
            "Local execution comparison; a gold-query timeout makes the local result "
            "unavailable and is scored false. Official BIRD evaluation follows."
        ),
        "official_evaluation_timeout_seconds": 30,
        "retry_policy": "retry only API failures with an empty SQL output",
        "results": results,
        "summary": summarize(results, dataset_size),
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    configure_windows_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema-mode", choices=("full", "compact"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--api-timeout", type=float, default=30.0)
    parser.add_argument("--api-max-retries", type=int, default=1)
    parser.add_argument("--sql-timeout", type=float, default=10.0)
    parser.add_argument("--gold-sql-timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit 必须是正整数。")
    if (
        args.api_timeout <= 0
        or args.api_max_retries < 0
        or args.sql_timeout <= 0
        or args.gold_sql_timeout <= 0
    ):
        raise SystemExit("API timeout/retry 参数无效。")

    output = args.output or DAY_DIR / f"bird_{args.schema_mode}_schema_results.json"
    all_cases = load_cases()
    cases = all_cases[: args.limit] if args.limit else all_cases
    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit("未检测到 ZAI_API_KEY。请先在当前 PowerShell 窗口安全设置。")
    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    client = ZhipuAiClient(
        api_key=api_key, timeout=args.api_timeout, max_retries=args.api_max_retries
    )
    print(
        f"BIRD设置：mode={args.schema_mode}, model={model}, "
        f"timeout={args.api_timeout:g}s, max_retries={args.api_max_retries}"
    )

    results_by_id: dict[str, dict[str, Any]] = {}
    if args.resume and output.is_file():
        existing = json.loads(output.read_text(encoding="utf-8"))
        results_by_id = {item["id"]: item for item in existing.get("results", [])}
        print(f"续跑模式：已读取 {len(results_by_id)} 条已有结果。")

    schema_cache: dict[str, tuple[str, int]] = {}
    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        if args.resume and case_id in results_by_id:
            if results_by_id[case_id].get("generated_sql"):
                print(f"[{index}/{len(cases)}] {case_id}: 已完成，跳过 API。")
                continue
            print(f"[{index}/{len(cases)}] {case_id}: 上次未获得SQL，重新调用API。")

        db_id = case["db_id"]
        db_path = database_path(db_id)
        if not db_path.is_file():
            raise FileNotFoundError(f"找不到数据库：{db_path}")
        if db_id not in schema_cache:
            if args.schema_mode == "full":
                schema = extract_schema(db_path)
                table_count = schema.upper().count("CREATE TABLE ")
            else:
                schema, table_names = build_compact_schema(db_path)
                table_count = len(table_names)
            schema_cache[db_id] = (schema, table_count)
        schema, table_count = schema_cache[db_id]
        prompt = build_prompt(schema, case["question"], case["evidence"])

        print(f"[{index}/{len(cases)}] {case_id} [{db_id}]: 调用 {model}...")
        started = time.perf_counter()
        generated_sql = ""
        call_error = finish_reason = None
        prompt_tokens = completion_tokens = total_tokens = None
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "disabled"},
                temperature=0.0,
                max_tokens=768,
                timeout=args.api_timeout,
            )
            choice = response.choices[0]
            generated_sql = clean_sql(choice.message.content)
            finish_reason = choice.finish_reason
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if not generated_sql:
                call_error = "API 返回内容为空。"
        except Exception as exc:
            call_error = f"{type(exc).__name__}: {exc}"

        latency = round(time.perf_counter() - started, 3)
        print(
            f"[{index}/{len(cases)}] {case_id}: "
            f"执行预测SQL（上限{args.sql_timeout:g}秒）..."
        )
        predicted = execute_readonly(
            db_path, generated_sql, query_timeout_seconds=args.sql_timeout
        ) if generated_sql else {
            "success": False, "columns": [], "rows": [], "error": call_error
        }
        print(
            f"[{index}/{len(cases)}] {case_id}: "
            f"执行标准SQL（上限{args.gold_sql_timeout:g}秒）..."
        )
        gold = execute_readonly(
            db_path,
            case["gold_sql"],
            query_timeout_seconds=args.gold_sql_timeout,
        )
        is_correct = bool(
            predicted["success"]
            and gold["success"]
            and preliminary_match(predicted["rows"], gold["rows"], case["gold_order_matters"])
        )
        result = {
            **case,
            "schema_mode": args.schema_mode,
            "schema_character_count": len(schema),
            "table_count": table_count,
            "generated_sql": generated_sql,
            "execution_success": bool(predicted["success"]),
            "local_evaluation_available": bool(gold["success"]),
            "gold_execution_success": bool(gold["success"]),
            "gold_execution_error": gold["error"],
            "preliminary_is_correct": is_correct,
            "predicted_row_count": len(predicted["rows"]),
            "gold_row_count": len(gold["rows"]),
            "error": call_error or predicted["error"],
            "latency_seconds": latency,
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        results_by_id[case_id] = result
        ordered = [results_by_id[x["id"]] for x in all_cases if x["id"] in results_by_id]
        save_report(output, model, args.schema_mode, ordered, len(all_cases))
        if not gold["success"]:
            label = "EVAL_TIMEOUT"
        else:
            label = "CORRECT" if is_correct else "WRONG"
        print(
            f"[{index}/{len(cases)}] {case_id}: {label}, "
            f"execution_success={predicted['success']}, latency={latency}s"
        )
        if not gold["success"]:
            print(
                f"[{index}/{len(cases)}] {case_id}: 标准SQL本地执行超时，"
                "已记录并继续；官方评测将按错误处理。"
            )

    ordered = [results_by_id[x["id"]] for x in all_cases if x["id"] in results_by_id]
    print("\nBIRD Mini-Dev 本地汇总（非官方指标）：")
    print(json.dumps(summarize(ordered, len(all_cases)), ensure_ascii=False, indent=2))
    print(f"结果已保存：{output.resolve()}")


if __name__ == "__main__":
    main()

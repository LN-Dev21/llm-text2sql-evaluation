"""使用 Zhipu GLM 在 Spider 开发子集上运行 full-schema zero-shot 基线。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from zai import ZhipuAiClient


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))

from build_prompt import build_prompt  # noqa: E402
from extract_schema import extract_schema  # noqa: E402

from inspect_spider import DEFAULT_SPIDER_ROOT, database_path  # noqa: E402


DEFAULT_SUBSET = DAY_DIR / "spider_subset.json"
DEFAULT_OUTPUT = DAY_DIR / "spider_baseline_results.json"


def clean_sql(text: str) -> str:
    value = (text or "").strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fenced:
        value = fenced.group(1).strip()
    return value


def execute_readonly(db_path: Path, sql: str) -> dict[str, Any]:
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.I):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": "只允许执行 SELECT 或 WITH 查询。",
        }
    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            cursor = connection.execute(sql)
            return {
                "success": True,
                "columns": [item[0] for item in cursor.description],
                "rows": [list(row) for row in cursor.fetchall()],
                "error": None,
            }
    except Exception as exc:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def normalize_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    return value


def normalized_rows(rows: list[list[Any]], order_matters: bool) -> list[list[Any]]:
    normalized = [[normalize_value(value) for value in row] for row in rows]
    if not order_matters:
        normalized.sort(key=lambda row: tuple((type(v).__name__, repr(v)) for v in row))
    return normalized


def preliminary_match(
    predicted_rows: list[list[Any]],
    gold_rows: list[list[Any]],
    order_matters: bool,
) -> bool:
    return normalized_rows(predicted_rows, order_matters) == normalized_rows(
        gold_rows, order_matters
    )


def summarize(results: list[dict[str, Any]], dataset_size: int) -> dict[str, Any]:
    completed = len(results)
    execution_successes = sum(bool(item["execution_success"]) for item in results)
    correct = sum(bool(item["preliminary_is_correct"]) for item in results)
    total_tokens = sum((item.get("total_tokens") or 0) for item in results)
    total_latency = sum((item.get("latency_seconds") or 0.0) for item in results)
    return {
        "dataset_size": dataset_size,
        "completed": completed,
        "execution_success_count": execution_successes,
        "preliminary_correct_count": correct,
        "execution_success_rate": round(execution_successes / completed, 4)
        if completed
        else 0.0,
        "preliminary_execution_accuracy": round(correct / completed, 4)
        if completed
        else 0.0,
        "average_latency_seconds": round(total_latency / completed, 3)
        if completed
        else 0.0,
        "total_tokens": total_tokens,
    }


def save_report(
    output_path: Path,
    model: str,
    spider_root: Path,
    dataset_size: int,
    results: list[dict[str, Any]],
    experiment_name: str = "Spider 1.0 multi-database full-schema zero-shot baseline",
    schema_source: str = "automatically extracted from each SQLite database",
    schema_selection_file: str | None = None,
) -> None:
    report = {
        "experiment": experiment_name,
        "model": model,
        "spider_root": str(spider_root.resolve()),
        "schema_source": schema_source,
        "schema_selection_file": schema_selection_file,
        "gold_sql_sent_to_model": False,
        "metric_note": (
            "This is a local development-time row comparison, not official Spider "
            "Test Suite Accuracy. Official evaluation will be integrated separately."
        ),
        "results": results,
        "summary": summarize(results, dataset_size),
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider-root", type=Path, default=DEFAULT_SPIDER_ROOT)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--schema-selections", type=Path)
    parser.add_argument(
        "--experiment-name",
        default="Spider 1.0 multi-database full-schema zero-shot baseline",
    )
    parser.add_argument(
        "--schema-source-label",
        help="写入结果元数据的Schema来源说明；未设置时按是否提供选择文件自动填写。",
    )
    parser.add_argument(
        "--api-timeout",
        type=float,
        default=30.0,
        help="单次API请求超时秒数，默认30秒。",
    )
    parser.add_argument(
        "--api-max-retries",
        type=int,
        default=1,
        help="SDK在请求失败后的自动重试次数，默认1次。",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit 必须是正整数。")
    if args.api_timeout <= 0:
        raise SystemExit("--api-timeout 必须大于0。")
    if args.api_max_retries < 0:
        raise SystemExit("--api-max-retries 不能为负数。")
    if not args.subset.is_file():
        raise SystemExit(f"找不到子集文件：{args.subset}")

    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    all_cases: list[dict[str, Any]] = subset["cases"]
    cases = all_cases[: args.limit] if args.limit else all_cases
    spider_root = args.spider_root.resolve()

    selections_by_id: dict[str, dict[str, Any]] = {}
    if args.schema_selections is not None:
        if not args.schema_selections.is_file():
            raise SystemExit(f"找不到Schema选择文件：{args.schema_selections}")
        selection_report = json.loads(
            args.schema_selections.read_text(encoding="utf-8")
        )
        selections_by_id = {
            item["id"]: item for item in selection_report.get("cases", [])
        }
        missing_selections = [
            case["id"] for case in cases if case["id"] not in selections_by_id
        ]
        if missing_selections:
            raise SystemExit(
                f"Schema选择文件缺少{len(missing_selections)}题：{missing_selections}"
            )

    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "未检测到 ZAI_API_KEY。请先在当前 PowerShell 窗口安全设置 API Key。"
        )
    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    client = ZhipuAiClient(
        api_key=api_key,
        timeout=args.api_timeout,
        max_retries=args.api_max_retries,
    )
    print(
        f"API设置：timeout={args.api_timeout:g}s, "
        f"max_retries={args.api_max_retries}"
    )

    results_by_id: dict[str, dict[str, Any]] = {}
    if args.resume and args.output.is_file():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        results_by_id = {item["id"]: item for item in existing.get("results", [])}
        print(f"续跑模式：已读取 {len(results_by_id)} 条已有结果。")

    schema_cache: dict[str, str] = {}
    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        if args.resume and case_id in results_by_id:
            existing_result = results_by_id[case_id]
            if existing_result.get("generated_sql"):
                print(f"[{index}/{len(cases)}] {case_id}: 已完成，跳过 API。")
                continue
            print(f"[{index}/{len(cases)}] {case_id}: 上次未获得SQL，重新调用API。")

        db_id = case["db_id"]
        db_path = database_path(spider_root, db_id)
        if not db_path.is_file():
            raise SystemExit(f"找不到数据库：{db_path}")
        selection = selections_by_id.get(case_id)
        if selection is not None:
            schema = selection["selected_schema"]
            selected_tables = selection["selected_tables"]
            schema_mode = "selected_schema"
        else:
            if db_id not in schema_cache:
                schema_cache[db_id] = extract_schema(db_path)
            schema = schema_cache[db_id]
            selected_tables = None
            schema_mode = "full_schema"
        prompt = build_prompt(schema, case["question"])

        print(f"[{index}/{len(cases)}] {case_id} [{db_id}]: 调用 {model}...")
        started = time.perf_counter()
        generated_sql = ""
        call_error = None
        finish_reason = None
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "disabled"},
                temperature=0.0,
                max_tokens=512,
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
        predicted = (
            execute_readonly(db_path, generated_sql)
            if generated_sql
            else {"success": False, "columns": [], "rows": [], "error": call_error}
        )
        gold = execute_readonly(db_path, case["gold_sql"])
        if not gold["success"]:
            raise RuntimeError(f"{case_id} 的标准 SQL 执行失败：{gold['error']}")

        is_correct = bool(
            predicted["success"]
            and preliminary_match(
                predicted["rows"], gold["rows"], case["gold_order_matters"]
            )
        )
        result = {
            "id": case_id,
            "source_index": case["source_index"],
            "db_id": db_id,
            "question": case["question"],
            "schema_mode": schema_mode,
            "selected_tables": selected_tables,
            "selected_table_count": len(selected_tables) if selected_tables else None,
            "schema_character_count": len(schema),
            "generated_sql": generated_sql,
            "gold_sql": case["gold_sql"],
            "gold_order_matters": case["gold_order_matters"],
            "execution_success": bool(predicted["success"]),
            "preliminary_is_correct": is_correct,
            "predicted_columns": predicted["columns"],
            "predicted_rows": predicted["rows"],
            "gold_columns": gold["columns"],
            "gold_rows": gold["rows"],
            "error": call_error or predicted["error"],
            "latency_seconds": latency,
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        results_by_id[case_id] = result
        ordered = [
            results_by_id[item["id"]]
            for item in all_cases
            if item["id"] in results_by_id
        ]
        save_report(
            args.output,
            model,
            spider_root,
            len(all_cases),
            ordered,
            experiment_name=args.experiment_name,
            schema_source=(
                args.schema_source_label
                or (
                    "heuristic lexical schema linking"
                    if selections_by_id
                    else "automatically extracted full SQLite schema"
                )
            ),
            schema_selection_file=(
                str(args.schema_selections.resolve())
                if args.schema_selections is not None
                else None
            ),
        )
        label = "CORRECT" if is_correct else "WRONG"
        print(
            f"[{index}/{len(cases)}] {case_id}: {label}, "
            f"execution_success={predicted['success']}, latency={latency}s"
        )

    ordered = [
        results_by_id[item["id"]]
        for item in all_cases
        if item["id"] in results_by_id
    ]
    summary = summarize(ordered, len(all_cases))
    print("\nSpider 开发子集汇总（非官方指标）：")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"结果已保存：{args.output.resolve()}")


if __name__ == "__main__":
    main()

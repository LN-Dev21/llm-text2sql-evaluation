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


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DAY2_DIR = PROJECT_ROOT / "day2_auto_schema"
sys.path.insert(0, str(DAY2_DIR))

from build_prompt import build_prompt  # noqa: E402
from extract_schema import DEFAULT_DB, extract_schema  # noqa: E402


DEFAULT_CASES = ROOT / "cases.json"
DEFAULT_OUTPUT = ROOT / "batch_results.json"


def load_cases(path: Path) -> list[dict[str, str]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases.json必须是非空JSON数组。")

    required = {"id", "difficulty", "question", "gold_sql"}
    seen_ids: set[str] = set()
    for case in cases:
        missing = required - set(case)
        if missing:
            raise ValueError(f"测试题缺少字段：{sorted(missing)}")
        if case["id"] in seen_ids:
            raise ValueError(f"测试题ID重复：{case['id']}")
        seen_ids.add(case["id"])
    return cases


def clean_sql(text: str) -> str:
    value = (text or "").strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.I | re.S)
    if fenced:
        value = fenced.group(1).strip()
    return value


def normalize_rows(rows: list[list[Any]]) -> list[list[Any]]:
    normalized: list[list[Any]] = []
    for row in rows:
        normalized.append(
            [round(value, 6) if isinstance(value, float) else value for value in row]
        )
    return normalized


def execute_readonly(db_path: Path, sql: str) -> dict[str, Any]:
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, flags=re.I):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": "只允许执行SELECT或WITH查询。",
        }

    try:
        database_uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            cursor = connection.execute(sql)
            columns = [item[0] for item in cursor.description]
            rows = [list(row) for row in cursor.fetchall()]
        return {"success": True, "columns": columns, "rows": rows, "error": None}
    except Exception as exc:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def summarize(results: list[dict[str, Any]], dataset_size: int) -> dict[str, Any]:
    completed = len(results)
    execution_successes = sum(bool(item["execution_success"]) for item in results)
    correct = sum(bool(item["is_correct"]) for item in results)
    total_tokens = sum((item.get("total_tokens") or 0) for item in results)
    return {
        "dataset_size": dataset_size,
        "completed": completed,
        "execution_success_count": execution_successes,
        "correct_count": correct,
        "execution_success_rate": round(execution_successes / completed, 4) if completed else 0.0,
        "execution_accuracy": round(correct / completed, 4) if completed else 0.0,
        "total_tokens": total_tokens,
    }


def save_report(
    output_path: Path,
    model: str,
    db_path: Path,
    dataset_size: int,
    results: list[dict[str, Any]],
) -> None:
    report = {
        "experiment": "full-schema zero-shot local batch baseline",
        "model": model,
        "database_file": str(db_path.resolve()),
        "schema_source": "automatically extracted from SQLite",
        "gold_sql_sent_to_model": False,
        "results": results,
        "summary": summarize(results, dataset_size),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def validate_gold_sql(cases: list[dict[str, str]], db_path: Path) -> None:
    failures = 0
    for case in cases:
        execution = execute_readonly(db_path, case["gold_sql"])
        if execution["success"]:
            print(f"{case['id']}: OK, rows={len(execution['rows'])}")
        else:
            failures += 1
            print(f"{case['id']}: FAILED, {execution['error']}")
    if failures:
        raise SystemExit(f"有{failures}条标准SQL验证失败，禁止开始API实验。")
    print(f"全部{len(cases)}条标准SQL验证通过。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用完整自动Schema批量评测Text-to-SQL零样本基线"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    db_path = args.db.resolve()
    cases_path = args.cases.resolve()
    output_path = args.output.resolve()
    if not db_path.is_file():
        raise SystemExit(f"找不到数据库文件：{db_path}")
    if not cases_path.is_file():
        raise SystemExit(f"找不到测试集：{cases_path}")

    cases = load_cases(cases_path)
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit必须是正整数。")
        selected_cases = cases[: args.limit]
    else:
        selected_cases = cases

    if args.validate_only:
        validate_gold_sql(selected_cases, db_path)
        return

    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit("未检测到ZAI_API_KEY，批量实验尚未开始。")

    model = os.getenv("ZAI_MODEL", "glm-4.5-air")
    schema = extract_schema(db_path)
    client = ZhipuAiClient(api_key=api_key)

    results_by_id: dict[str, dict[str, Any]] = {}
    if args.resume and output_path.is_file():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        results_by_id = {item["id"]: item for item in existing.get("results", [])}
        print(f"续跑模式：已读取{len(results_by_id)}条已有结果。")

    for index, case in enumerate(selected_cases, start=1):
        case_id = case["id"]
        if args.resume and case_id in results_by_id:
            print(f"[{index}/{len(selected_cases)}] {case_id}: 已完成，跳过API调用。")
            continue

        # Only schema and question enter the prompt. Gold SQL stays local for evaluation.
        prompt = build_prompt(schema, case["question"])
        print(f"[{index}/{len(selected_cases)}] {case_id}: 调用{model}...")
        start_time = time.perf_counter()

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
            )
            message = response.choices[0].message
            generated_sql = clean_sql(message.content)
            finish_reason = response.choices[0].finish_reason
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if not generated_sql:
                call_error = "API返回内容为空。"
        except Exception as exc:
            call_error = f"{type(exc).__name__}: {exc}"

        latency_seconds = round(time.perf_counter() - start_time, 3)
        predicted = execute_readonly(db_path, generated_sql) if generated_sql else {
            "success": False,
            "columns": [],
            "rows": [],
            "error": call_error or "未生成SQL。",
        }
        gold = execute_readonly(db_path, case["gold_sql"])
        if not gold["success"]:
            raise RuntimeError(f"{case_id}的标准SQL执行失败：{gold['error']}")

        is_correct = bool(
            predicted["success"]
            and normalize_rows(predicted["rows"]) == normalize_rows(gold["rows"])
        )
        result = {
            "id": case_id,
            "difficulty": case["difficulty"],
            "question": case["question"],
            "generated_sql": generated_sql,
            "gold_sql": case["gold_sql"],
            "execution_success": bool(predicted["success"]),
            "is_correct": is_correct,
            "predicted_columns": predicted["columns"],
            "predicted_rows": predicted["rows"],
            "gold_columns": gold["columns"],
            "gold_rows": gold["rows"],
            "error": call_error or predicted["error"],
            "latency_seconds": latency_seconds,
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        results_by_id[case_id] = result

        ordered_results = [
            results_by_id[item["id"]]
            for item in cases
            if item["id"] in results_by_id
        ]
        save_report(output_path, model, db_path, len(cases), ordered_results)
        status = "CORRECT" if is_correct else "WRONG"
        print(
            f"[{index}/{len(selected_cases)}] {case_id}: {status}, "
            f"execution_success={predicted['success']}, latency={latency_seconds}s"
        )

    final_results = [
        results_by_id[item["id"]]
        for item in cases
        if item["id"] in results_by_id
    ]
    save_report(output_path, model, db_path, len(cases), final_results)
    print("\n批量实验汇总：")
    print(json.dumps(summarize(final_results, len(cases)), ensure_ascii=False, indent=2))
    print(f"结果已保存：{output_path}")


if __name__ == "__main__":
    main()


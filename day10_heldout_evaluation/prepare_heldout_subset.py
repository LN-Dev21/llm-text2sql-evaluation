"""从未参与开发实验的大Schema数据库中确定性抽取150题held-out子集。"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY4_DIR = PROJECT_ROOT / "day4_spider_subset"
sys.path.insert(0, str(DAY4_DIR))

from prepare_subset import complexity_score  # noqa: E402
from inspect_spider import database_path  # noqa: E402


SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"
SOURCE = SPIDER_ROOT / "train_others.json"
OUTPUT = DAY_DIR / "heldout_subset.json"
QUOTAS = {"academic": 38, "imdb": 38, "scholar": 37, "yelp": 37}
DEVELOPMENT_DATABASES = {
    "student_transcripts_tracking", "dog_kennels", "car_1",
    "concert_singer", "pets_1", "course_teach", "world_1",
}


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip().lower())


def execute_gold(db_path: Path, sql: str) -> tuple[bool, int | None, str | None]:
    try:
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(sql).fetchall()
        return True, len(rows), None
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def select_evenly(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    ranked = sorted(items, key=lambda item: (item["sampling_complexity_score"], item["source_index"]))
    if len(ranked) < count:
        raise ValueError(f"可执行且去重后只有{len(ranked)}题，无法抽取{count}题。")
    positions = [round(i * (len(ranked)-1)/(count-1)) for i in range(count)]
    if len(set(positions)) != count:
        raise RuntimeError("均匀抽样位置出现重复。")
    return [ranked[position] for position in positions]


def main() -> None:
    overlap = set(QUOTAS) & DEVELOPMENT_DATABASES
    if overlap:
        raise RuntimeError(f"held-out数据库与开发数据库重叠：{sorted(overlap)}")
    source: list[dict[str, Any]] = json.loads(SOURCE.read_text(encoding="utf-8"))
    indexed = [dict(item, source_index=index) for index, item in enumerate(source)]
    selected_cases: list[dict[str, Any]] = []
    database_reports = []

    for db_id, quota in QUOTAS.items():
        db_path = database_path(SPIDER_ROOT, db_id)
        candidates = [item for item in indexed if item["db_id"] == db_id]
        seen: set[str] = set()
        valid: list[dict[str, Any]] = []
        duplicate_count = execution_failure_count = 0
        for item in candidates:
            signature = normalized_sql(item["query"])
            if signature in seen:
                duplicate_count += 1
                continue
            seen.add(signature)
            success, row_count, error = execute_gold(db_path, item["query"])
            if not success:
                execution_failure_count += 1
                continue
            valid.append({
                "id": f"spider_train_others_{item['source_index']:04d}",
                "source": "Spider 1.0 train_others.json",
                "source_index": item["source_index"], "db_id": db_id,
                "question": item["question"], "gold_sql": item["query"],
                "sampling_complexity_score": complexity_score(item),
                "gold_order_matters": bool(item["sql"].get("orderBy")),
                "gold_execution_success": True, "gold_result_row_count": row_count,
            })
        selected = select_evenly(valid, quota)
        selected_cases.extend(selected)
        database_reports.append({
            "db_id": db_id, "raw_question_count": len(candidates),
            "duplicate_sql_removed": duplicate_count,
            "gold_execution_failures_removed": execution_failure_count,
            "eligible_unique_executable_count": len(valid), "selected_count": len(selected),
        })

    ids = [item["id"] for item in selected_cases]
    if len(selected_cases) != 150 or len(ids) != len(set(ids)):
        raise RuntimeError("held-out子集数量或ID唯一性检查失败。")
    report = {
        "dataset": "Spider 1.0 train_others internal held-out subset",
        "role": "one-time held-out confirmation after development configuration freeze",
        "case_count": len(selected_cases), "database_count": len(QUOTAS),
        "selection": {
            "databases_and_quotas": QUOTAS,
            "development_databases_excluded": sorted(DEVELOPMENT_DATABASES),
            "duplicate_policy": "remove identical normalized gold SQL within each database",
            "sampling_policy": "deterministic even sampling over local SQL complexity score",
            "sampling_note": "complexity score is a local stratification heuristic, not official Spider hardness",
            "database_reports": database_reports,
        },
        "configuration_frozen_before_generation": True,
        "schema_linking_configuration": "Exp2 lexical Top-4 plus foreign-key paths",
        "gold_sql_sent_to_model": False, "cases": selected_cases,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成held-out子集：{len(selected_cases)}题，{len(QUOTAS)}个未见数据库。")
    for item in database_reports:
        print(f"- {item['db_id']}: raw={item['raw_question_count']}, "
              f"eligible={item['eligible_unique_executable_count']}, selected={item['selected_count']}, "
              f"duplicates_removed={item['duplicate_sql_removed']}, "
              f"execution_failures_removed={item['gold_execution_failures_removed']}")
    scores = [item["sampling_complexity_score"] for item in selected_cases]
    print(f"复杂度分数范围：{min(scores)}–{max(scores)}")
    print(f"子集文件：{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()

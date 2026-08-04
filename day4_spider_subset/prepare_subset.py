"""从 Spider 1.0 dev 中生成跨数据库、去同义重复的开发用小样本。"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from inspect_spider import DEFAULT_SPIDER_ROOT, database_path, read_json


DAY_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = DAY_DIR / "spider_subset.json"
DEFAULT_DATABASES = ("concert_singer", "pets_1", "course_teach", "world_1")


def complexity_score(item: dict[str, Any]) -> int:
    """仅为均匀抽样服务的启发式结构分数，不是 Spider 官方难度。"""
    sql = item["sql"]
    query = item["query"].upper()
    score = 0
    score += query.count(" JOIN ") * 2
    score += len(sql.get("where") or []) // 2
    score += len(sql.get("groupBy") or []) * 2
    score += 2 if sql.get("having") else 0
    score += 1 if sql.get("orderBy") else 0
    score += 1 if sql.get("limit") is not None else 0
    score += 3 * sum(bool(sql.get(key)) for key in ("intersect", "union", "except"))
    score += query.count("SELECT") - 1
    return score


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip().lower())


def select_evenly(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen_sql: set[str] = set()
    for item in items:
        signature = normalized_sql(item["query"])
        if signature not in seen_sql:
            seen_sql.add(signature)
            unique.append(item)

    ranked = sorted(
        unique,
        key=lambda item: (complexity_score(item), item["source_index"]),
    )
    if len(ranked) < count:
        raise ValueError(f"去重后只有 {len(ranked)} 道题，无法选择 {count} 道")
    if count == 1:
        return [ranked[len(ranked) // 2]]

    positions = [round(i * (len(ranked) - 1) / (count - 1)) for i in range(count)]
    return [ranked[position] for position in positions]


def execute_gold(db_path: Path, sql: str) -> int:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        cursor = connection.execute(sql)
        return len(cursor.fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spider-root", type=Path, default=DEFAULT_SPIDER_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-database", type=int, default=5)
    parser.add_argument("--databases", nargs="+", default=list(DEFAULT_DATABASES))
    args = parser.parse_args()
    if args.per_database <= 0:
        raise SystemExit("--per-database 必须是正整数")

    spider_root = args.spider_root.resolve()
    dev: list[dict[str, Any]] = read_json(spider_root / "dev.json")
    requested = set(args.databases)
    available = {item["db_id"] for item in dev}
    unknown = requested - available
    if unknown:
        raise SystemExit(f"dev.json 中不存在数据库：{sorted(unknown)}")

    indexed = [dict(item, source_index=index) for index, item in enumerate(dev)]
    subset: list[dict[str, Any]] = []
    for db_id in args.databases:
        candidates = [item for item in indexed if item["db_id"] == db_id]
        selected = select_evenly(candidates, args.per_database)
        db_path = database_path(spider_root, db_id)
        for item in selected:
            row_count = execute_gold(db_path, item["query"])
            subset.append(
                {
                    "id": f"spider_dev_{item['source_index']:04d}",
                    "source": "Spider 1.0 dev.json",
                    "source_index": item["source_index"],
                    "db_id": db_id,
                    "question": item["question"],
                    "gold_sql": item["query"],
                    "sampling_complexity_score": complexity_score(item),
                    "gold_order_matters": bool(item["sql"].get("orderBy")),
                    "gold_execution_success": True,
                    "gold_result_row_count": row_count,
                }
            )

    report = {
        "dataset": "Spider 1.0 development subset",
        "selection": {
            "databases": args.databases,
            "questions_per_database": args.per_database,
            "duplicate_policy": "remove identical normalized gold SQL within each database",
            "sampling_note": (
                "sampling_complexity_score is a local stratification heuristic, "
                "not the official Spider hardness label"
            ),
        },
        "gold_sql_sent_to_model": False,
        "case_count": len(subset),
        "cases": subset,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"已生成 {len(subset)} 道题，来自 {len(args.databases)} 个数据库。")
    for case in subset:
        print(
            f"{case['id']} [{case['db_id']}] "
            f"score={case['sampling_complexity_score']}: {case['question']}"
        )
    print(f"子集文件：{args.output.resolve()}")


if __name__ == "__main__":
    main()

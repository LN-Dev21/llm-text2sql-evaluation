"""调用智谱 Embedding-3，为 Exp3 所需问题和表描述建立本地缓存。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from zai import ZhipuAiClient


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY7_DIR = PROJECT_ROOT / "day7_lexical_schema_linking"
sys.path.insert(0, str(DAY7_DIR))

from lexical_schema_linker import inspect_database  # noqa: E402
from hybrid_schema_linker import cache_key, table_description  # noqa: E402


DEFAULT_SUBSET = PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
DEFAULT_CACHE = DAY_DIR / "embedding_cache.json"
SPIDER_ROOT = PROJECT_ROOT / "data" / "spider_data"


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--model", default="embedding-3")
    parser.add_argument("--dimensions", type=int, choices=(256, 512, 1024, 2048), default=512)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--api-timeout", type=float, default=30.0)
    parser.add_argument("--api-max-retries", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 64:
        raise SystemExit("--batch-size必须在1到64之间。")

    api_key = os.getenv("ZAI_API_KEY")
    if not api_key:
        raise SystemExit("未检测到ZAI_API_KEY，请先在当前PowerShell窗口安全设置。")

    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    texts: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        if text not in seen:
            seen.add(text)
            texts.append(text)

    for case in subset["cases"]:
        add(case["question"])
        db_id = case["db_id"]
        db_path = SPIDER_ROOT / "database" / db_id / f"{db_id}.sqlite"
        for table in inspect_database(db_path).values():
            add(table_description(table))

    if args.cache.exists():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))
        if cache.get("model") != args.model or cache.get("dimensions") != args.dimensions:
            raise SystemExit("现有缓存的模型或维度不同，请改用新缓存文件。")
    else:
        cache = {
            "model": args.model,
            "dimensions": args.dimensions,
            "gold_sql_sent_to_embedding_api": False,
            "items": {},
            "usage": {"requests": 0, "total_tokens": 0},
        }

    missing = [
        text for text in texts
        if cache_key(text, args.model, args.dimensions) not in cache["items"]
    ]
    print(f"需要的唯一文本：{len(texts)}；缓存命中：{len(texts)-len(missing)}；待请求：{len(missing)}")
    if not missing:
        print(f"Embedding缓存已完整：{args.cache.resolve()}")
        return

    client = ZhipuAiClient(
        api_key=api_key,
        timeout=args.api_timeout,
        max_retries=args.api_max_retries,
    )
    for start in range(0, len(missing), args.batch_size):
        batch = missing[start : start + args.batch_size]
        response = client.embeddings.create(
            model=args.model,
            input=batch,
            dimensions=args.dimensions,
        )
        data = sorted(response.data, key=lambda item: item.index)
        if len(data) != len(batch):
            raise RuntimeError("Embedding API返回条数与输入条数不一致。")
        for text, item in zip(batch, data):
            cache["items"][cache_key(text, args.model, args.dimensions)] = {
                "text": text,
                "embedding": list(item.embedding),
            }
        usage = getattr(response, "usage", None)
        cache["usage"]["requests"] += 1
        cache["usage"]["total_tokens"] += int(getattr(usage, "total_tokens", 0) or 0)
        save_cache(args.cache, cache)
        print(f"已缓存：{min(start+len(batch),len(missing))}/{len(missing)}")

    print(f"模型：{args.model}，维度：{args.dimensions}")
    print(f"累计请求：{cache['usage']['requests']}，累计tokens：{cache['usage']['total_tokens']}")
    print(f"Embedding缓存：{args.cache.resolve()}")


if __name__ == "__main__":
    main()

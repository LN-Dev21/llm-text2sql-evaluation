"""词法分数与文本向量相似度融合的简化 Schema Linking。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY7_DIR = PROJECT_ROOT / "day7_lexical_schema_linking"
sys.path.insert(0, str(DAY7_DIR))

from lexical_schema_linker import (  # noqa: E402
    TableInfo,
    expand_with_connector_tables,
    foreign_key_graph,
    inspect_database,
    render_schema,
    score_tables,
)


def cache_key(text: str, model: str, dimensions: int) -> str:
    payload = f"{model}\0{dimensions}\0{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def humanize(identifier: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier)
    return re.sub(r"\s+", " ", separated.replace("_", " ")).strip().lower()


def table_description(table: TableInfo) -> str:
    columns = ", ".join(humanize(column.name) for column in table.columns)
    return f"Database table {humanize(table.name)}. Columns: {columns}."


def load_embedding_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Embedding缓存不存在：{path}\n请先运行 prepare_embeddings.py。"
        )
    cache = json.loads(path.read_text(encoding="utf-8"))
    required = {"model", "dimensions", "items"}
    if not required.issubset(cache):
        raise ValueError(f"Embedding缓存格式不完整：{path}")
    return cache


def embedding_for(text: str, cache: dict[str, Any]) -> list[float]:
    key = cache_key(text, cache["model"], cache["dimensions"])
    item = cache["items"].get(key)
    if item is None or item.get("text") != text:
        raise KeyError(f"缓存中缺少文本向量：{text}")
    return item["embedding"]


def cosine_similarity(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        raise ValueError("两个向量维度不一致。")
    dot = sum(a * b for a, b in zip(first, second))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        return 0.0
    return dot / (first_norm * second_norm)


def score_tables_hybrid(
    question: str,
    tables: dict[str, TableInfo],
    cache: dict[str, Any],
    lexical_weight: float,
) -> list[dict[str, Any]]:
    if not 0 <= lexical_weight <= 1:
        raise ValueError("lexical_weight必须在0到1之间。")

    lexical_by_table = {
        item["table"]: item for item in score_tables(question, tables)
    }
    question_embedding = embedding_for(question, cache)
    rankings: list[dict[str, Any]] = []
    for table in tables.values():
        description = table_description(table)
        semantic_cosine = cosine_similarity(
            question_embedding, embedding_for(description, cache)
        )
        lexical_score = lexical_by_table[table.name]["score"]
        semantic_score = max(-1.0, min(1.0, semantic_cosine)) * 100.0
        combined = lexical_weight * lexical_score + (1 - lexical_weight) * semantic_score
        rankings.append(
            {
                "table": table.name,
                "score": round(combined, 3),
                "lexical_score": round(lexical_score, 3),
                "semantic_cosine": round(semantic_cosine, 6),
                "semantic_score": round(semantic_score, 3),
                "description": description,
            }
        )
    return sorted(rankings, key=lambda item: (-item["score"], item["table"].lower()))


def link_schema_hybrid(
    question: str,
    db_path: Path,
    cache: dict[str, Any],
    top_k: int = 4,
    lexical_weight: float = 0.5,
) -> dict[str, Any]:
    tables = inspect_database(db_path)
    rankings = score_tables_hybrid(question, tables, cache, lexical_weight)
    seed_tables = [item["table"] for item in rankings[: min(top_k, len(rankings))]]
    selected_tables = expand_with_connector_tables(
        seed_tables, foreign_key_graph(tables)
    )
    return {
        "seed_tables": seed_tables,
        "selected_tables": selected_tables,
        "selected_schema": render_schema(tables, selected_tables),
        "ranked_tables": rankings,
        "full_table_count": len(tables),
    }

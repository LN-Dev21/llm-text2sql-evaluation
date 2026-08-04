"""置信度感知的动态词法 Schema Linking 与完整 Schema 安全回退。"""

from __future__ import annotations

import math
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
    render_schema,
)


def apply_adaptive_policy(
    tables: dict[str, TableInfo],
    rankings: list[dict[str, Any]],
    full_schema: str,
    *,
    small_schema_threshold: int,
    seed_fraction: float,
    min_cutoff_gap: float,
    add_one_hop_neighbors: bool,
    near_full_fraction: float = 0.9,
) -> dict[str, Any]:
    table_count = len(tables)
    all_tables = sorted(tables, key=str.lower)
    if table_count <= small_schema_threshold:
        return {
            "selection_mode": "full_schema_fallback",
            "fallback_reason": "small_schema",
            "seed_tables": all_tables,
            "selected_tables": all_tables,
            "selected_schema": full_schema,
            "cutoff_gap": None,
        }

    seed_count = min(table_count, max(4, math.ceil(seed_fraction * table_count)))
    cutoff_gap = (
        rankings[seed_count - 1]["score"] - rankings[seed_count]["score"]
        if seed_count < table_count
        else float("inf")
    )
    if cutoff_gap < min_cutoff_gap:
        return {
            "selection_mode": "full_schema_fallback",
            "fallback_reason": "ambiguous_cutoff",
            "seed_tables": [item["table"] for item in rankings[:seed_count]],
            "selected_tables": all_tables,
            "selected_schema": full_schema,
            "cutoff_gap": round(cutoff_gap, 3),
        }

    seed_tables = [item["table"] for item in rankings[:seed_count]]
    graph = foreign_key_graph(tables)
    selected = set(expand_with_connector_tables(seed_tables, graph))
    if add_one_hop_neighbors:
        for table in list(selected):
            selected.update(graph[table])
    selected_tables = sorted(selected, key=str.lower)
    if len(selected_tables) / table_count >= near_full_fraction:
        return {
            "selection_mode": "full_schema_fallback",
            "fallback_reason": "near_full_after_expansion",
            "seed_tables": seed_tables,
            "selected_tables": all_tables,
            "selected_schema": full_schema,
            "cutoff_gap": round(cutoff_gap, 3),
        }
    return {
        "selection_mode": "adaptive_selected_schema",
        "fallback_reason": None,
        "seed_tables": seed_tables,
        "selected_tables": selected_tables,
        "selected_schema": render_schema(tables, selected_tables),
        "cutoff_gap": round(cutoff_gap, 3),
    }

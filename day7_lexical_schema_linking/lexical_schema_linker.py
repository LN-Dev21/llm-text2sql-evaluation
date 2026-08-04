"""基于标识符词法匹配和外键路径扩展的简化 Schema Linking。"""

from __future__ import annotations

import itertools
import re
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz


GENERIC_TOKENS = {
    "a",
    "all",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "each",
    "find",
    "for",
    "from",
    "give",
    "has",
    "have",
    "how",
    "in",
    "is",
    "list",
    "many",
    "of",
    "on",
    "or",
    "show",
    "that",
    "the",
    "their",
    "there",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}

LOW_INFORMATION_IDENTIFIER_TOKENS = {
    "id",
    "code",
    "name",
    "number",
    "description",
    "detail",
    "type",
}


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    not_null: bool
    default_value: Any
    primary_key: bool


@dataclass(frozen=True)
class ForeignKeyInfo:
    from_column: str
    referenced_table: str
    referenced_column: str


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: tuple[ColumnInfo, ...]
    foreign_keys: tuple[ForeignKeyInfo, ...]


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def singularize(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    raw_tokens = re.findall(r"[A-Za-z0-9]+", separated.replace("_", " ").lower())
    return [singularize(token) for token in raw_tokens if token not in GENERIC_TOKENS]


def informative(tokens: list[str]) -> list[str]:
    selected = [token for token in tokens if token not in LOW_INFORMATION_IDENTIFIER_TOKENS]
    return selected or tokens


def identifier_alignment(identifier: str, question_tokens: list[str]) -> float:
    identifier_tokens = informative(tokenize(identifier))
    if not identifier_tokens or not question_tokens:
        return 0.0
    exact = sum(token in question_tokens for token in identifier_tokens)
    fuzzy_scores = [
        max(fuzz.ratio(token, question_token) for question_token in question_tokens)
        for token in identifier_tokens
    ]
    fuzzy_alignment = sum(fuzzy_scores) / len(fuzzy_scores)
    exact_boost = 18.0 * exact / len(identifier_tokens)
    return min(100.0, fuzzy_alignment + exact_boost)


def inspect_database(db_path: Path) -> dict[str, TableInfo]:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result: dict[str, TableInfo] = {}
        for table_name in table_names:
            quoted = quote_identifier(table_name)
            columns = tuple(
                ColumnInfo(
                    name=row[1],
                    data_type=row[2] or "TEXT",
                    not_null=bool(row[3]),
                    default_value=row[4],
                    primary_key=bool(row[5]),
                )
                for row in connection.execute(f"PRAGMA table_info({quoted})")
            )
            foreign_keys = tuple(
                ForeignKeyInfo(
                    from_column=row[3],
                    referenced_table=row[2],
                    referenced_column=row[4],
                )
                for row in connection.execute(f"PRAGMA foreign_key_list({quoted})")
            )
            result[table_name] = TableInfo(table_name, columns, foreign_keys)
    return result


def score_tables(question: str, tables: dict[str, TableInfo]) -> list[dict[str, Any]]:
    question_tokens = informative(tokenize(question))
    rankings: list[dict[str, Any]] = []
    for table in tables.values():
        table_score = identifier_alignment(table.name, question_tokens)
        column_scores = sorted(
            (
                (column.name, identifier_alignment(column.name, question_tokens))
                for column in table.columns
            ),
            key=lambda item: (-item[1], item[0].lower()),
        )
        best = column_scores[0][1] if column_scores else 0.0
        second = column_scores[1][1] if len(column_scores) > 1 else 0.0
        combined = 0.50 * table_score + 0.35 * best + 0.15 * second
        rankings.append(
            {
                "table": table.name,
                "score": round(combined, 3),
                "table_score": round(table_score, 3),
                "top_columns": [
                    {"column": name, "score": round(score, 3)}
                    for name, score in column_scores[:3]
                ],
            }
        )
    return sorted(rankings, key=lambda item: (-item["score"], item["table"].lower()))


def foreign_key_graph(tables: dict[str, TableInfo]) -> dict[str, set[str]]:
    canonical = {name.lower(): name for name in tables}
    graph = {name: set() for name in tables}
    for table in tables.values():
        for foreign_key in table.foreign_keys:
            referenced = canonical.get(foreign_key.referenced_table.lower())
            if referenced is not None:
                graph[table.name].add(referenced)
                graph[referenced].add(table.name)
    return graph


def shortest_path(graph: dict[str, set[str]], start: str, end: str) -> list[str]:
    queue: deque[list[str]] = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == end:
            return path
        for neighbor in sorted(graph[current], key=str.lower):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append([*path, neighbor])
    return []


def expand_with_connector_tables(
    seed_tables: list[str], graph: dict[str, set[str]]
) -> list[str]:
    selected = set(seed_tables)
    for first, second in itertools.combinations(seed_tables, 2):
        selected.update(shortest_path(graph, first, second))
    return sorted(selected, key=str.lower)


def render_schema(tables: dict[str, TableInfo], selected_tables: list[str]) -> str:
    selected_lookup = {name.lower() for name in selected_tables}
    statements: list[str] = []
    for table_name in selected_tables:
        table = tables[table_name]
        definitions: list[str] = []
        for column in table.columns:
            parts = [column.name, column.data_type]
            if column.primary_key:
                parts.append("PRIMARY KEY")
            if column.not_null and not column.primary_key:
                parts.append("NOT NULL")
            if column.default_value is not None:
                parts.extend(["DEFAULT", str(column.default_value)])
            definitions.append("    " + " ".join(parts))
        for foreign_key in table.foreign_keys:
            if foreign_key.referenced_table.lower() in selected_lookup:
                definitions.append(
                    "    "
                    f"FOREIGN KEY ({foreign_key.from_column}) "
                    f"REFERENCES {foreign_key.referenced_table}"
                    f"({foreign_key.referenced_column})"
                )
        statements.append(
            f"CREATE TABLE {table.name} (\n"
            + ",\n".join(definitions)
            + "\n);"
        )
    return "\n\n".join(statements)


def link_schema(question: str, db_path: Path, top_k: int = 4) -> dict[str, Any]:
    tables = inspect_database(db_path)
    rankings = score_tables(question, tables)
    seed_count = min(top_k, len(rankings))
    seed_tables = [item["table"] for item in rankings[:seed_count]]
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

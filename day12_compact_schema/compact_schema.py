"""将完整SQLite Schema序列化为保留标识符、类型和外键的紧凑文本。"""

from __future__ import annotations

import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DAY7_DIR = PROJECT_ROOT / "day7_lexical_schema_linking"
sys.path.insert(0, str(DAY7_DIR))

from lexical_schema_linker import TableInfo, inspect_database  # noqa: E402


def compact_type(data_type: str) -> str:
    value = " ".join((data_type or "TEXT").upper().split())
    return value


def render_compact_schema(tables: dict[str, TableInfo]) -> str:
    lines = ["SQLite schema (all tables and columns):"]
    for table_name in sorted(tables, key=str.lower):
        table = tables[table_name]
        columns = []
        for column in table.columns:
            suffix = " PK" if column.primary_key else ""
            columns.append(f"{column.name}:{compact_type(column.data_type)}{suffix}")
        lines.append(f"- {table.name}({', '.join(columns)})")
    foreign_keys = []
    for table_name in sorted(tables, key=str.lower):
        table = tables[table_name]
        for fk in table.foreign_keys:
            foreign_keys.append(
                f"- {table.name}.{fk.from_column} -> "
                f"{fk.referenced_table}.{fk.referenced_column}"
            )
    if foreign_keys:
        lines.append("Foreign keys:")
        lines.extend(foreign_keys)
    return "\n".join(lines)


def build_compact_schema(db_path: Path) -> tuple[str, list[str]]:
    tables = inspect_database(db_path)
    return render_compact_schema(tables), sorted(tables, key=str.lower)

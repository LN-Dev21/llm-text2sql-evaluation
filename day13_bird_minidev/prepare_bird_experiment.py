"""Validate BIRD Mini-Dev files and freeze the Day 13 experiment profile."""

from __future__ import annotations

import json
import ctypes
import sys
from collections import Counter
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
DATA_ROOT = PROJECT_ROOT / "data" / "bird_mini_dev" / "minidev" / "MINIDEV"
SOURCE = DATA_ROOT / "mini_dev_sqlite.json"
DATABASE_ROOT = DATA_ROOT / "dev_databases"
OUTPUT = DAY_DIR / "bird_experiment_profile.json"

sys.path.insert(0, str(PROJECT_ROOT / "day2_auto_schema"))
sys.path.insert(0, str(PROJECT_ROOT / "day12_compact_schema"))
from extract_schema import extract_schema  # noqa: E402
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


def main() -> None:
    configure_windows_console()
    if not SOURCE.is_file():
        raise SystemExit(f"找不到 BIRD Mini-Dev：{SOURCE}")
    cases = json.loads(SOURCE.read_text(encoding="utf-8"))
    required = {"question_id", "db_id", "question", "evidence", "SQL", "difficulty"}
    if len(cases) != 500:
        raise RuntimeError(f"预期500题，实际{len(cases)}题。")
    if any(not required.issubset(case) for case in cases):
        raise RuntimeError("至少一题缺少 BIRD 必需字段。")
    question_ids = [case["question_id"] for case in cases]
    if len(question_ids) != len(set(question_ids)):
        raise RuntimeError("question_id 存在重复。")

    counts = Counter(case["db_id"] for case in cases)
    profiles = []
    full_total = compact_total = 0
    for db_id in sorted(counts):
        db_path = database_path(db_id)
        if not db_path.is_file():
            raise FileNotFoundError(f"找不到数据库：{db_path}")
        full_schema = extract_schema(db_path)
        compact_schema, table_names = build_compact_schema(db_path)
        full_total += len(full_schema)
        compact_total += len(compact_schema)
        profiles.append({
            "db_id": db_id,
            "question_count": counts[db_id],
            "table_count": len(table_names),
            "full_schema_characters": len(full_schema),
            "compact_schema_characters": len(compact_schema),
            "character_reduction_rate": round(1 - len(compact_schema) / len(full_schema), 4),
        })

    report = {
        "dataset": "BIRD Mini-Dev SQLite",
        "source": "https://github.com/bird-bench/mini_dev",
        "license": "CC BY-SA 4.0",
        "role": "one-time cross-benchmark confirmation after method freeze",
        "case_count": len(cases),
        "database_count": len(counts),
        "difficulty_distribution": dict(sorted(Counter(case["difficulty"] for case in cases).items())),
        "full_schema_character_total_per_database": full_total,
        "compact_schema_character_total_per_database": compact_total,
        "schema_character_reduction_rate": round(1 - compact_total / full_total, 4),
        "configuration_frozen_before_api_generation": True,
        "model": "glm-4.5-air",
        "official_evidence_provided_to_both_methods": True,
        "gold_sql_sent_to_model": False,
        "retry_policy": "retry only API failures with an empty SQL output",
        "database_profiles": profiles,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n配置已冻结：{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()

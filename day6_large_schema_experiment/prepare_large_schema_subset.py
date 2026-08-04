"""复用 Day4 的确定性抽样逻辑，生成较大 Schema 的30题固定实验集。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE_SCRIPT = PROJECT_ROOT / "day4_spider_subset" / "prepare_subset.py"
OUTPUT = DAY_DIR / "large_schema_subset.json"
DATABASES = ("student_transcripts_tracking", "dog_kennels", "car_1")


def main() -> None:
    sys.path.insert(0, str(SOURCE_SCRIPT.parent))
    sys.argv = [
        str(SOURCE_SCRIPT),
        "--output",
        str(OUTPUT),
        "--per-database",
        "10",
        "--databases",
        *DATABASES,
    ]
    runpy.run_path(str(SOURCE_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()


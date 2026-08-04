"""复用 Day4 批量管线运行 Day6 的完整 Schema 基线。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE_SCRIPT = PROJECT_ROOT / "day4_spider_subset" / "run_spider_baseline.py"
SUBSET = DAY_DIR / "large_schema_subset.json"
OUTPUT = DAY_DIR / "full_schema_results.json"


def main() -> None:
    forwarded_arguments = sys.argv[1:]
    sys.path.insert(0, str(SOURCE_SCRIPT.parent))
    sys.argv = [
        str(SOURCE_SCRIPT),
        "--subset",
        str(SUBSET),
        "--output",
        str(OUTPUT),
        *forwarded_arguments,
    ]
    runpy.run_path(str(SOURCE_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()


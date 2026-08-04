"""复用共享批量管线运行 Exp3 混合 Schema Linking。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE_SCRIPT = PROJECT_ROOT / "day4_spider_subset" / "run_spider_baseline.py"
SUBSET = PROJECT_ROOT / "day6_large_schema_experiment" / "large_schema_subset.json"
SELECTIONS = DAY_DIR / "hybrid_schema_selections.json"
OUTPUT = DAY_DIR / "hybrid_schema_results.json"


def main() -> None:
    if not SELECTIONS.exists():
        raise SystemExit("尚未生成混合Schema选择文件，请先运行audit_hybrid_linking.py。")
    sys.path.insert(0, str(SOURCE_SCRIPT.parent))
    sys.argv = [
        str(SOURCE_SCRIPT), "--subset", str(SUBSET),
        "--schema-selections", str(SELECTIONS),
        "--experiment-name", "Exp3 lexical plus embedding schema linking",
        "--output", str(OUTPUT), *sys.argv[1:],
    ]
    runpy.run_path(str(SOURCE_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()

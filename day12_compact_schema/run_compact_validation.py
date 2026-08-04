"""在150题扩展验证集上运行紧凑完整Schema表示。"""

from __future__ import annotations
import runpy, sys
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE = PROJECT_ROOT/"day4_spider_subset"/"run_spider_baseline.py"

def main() -> None:
    selections = DAY_DIR/"compact_validation_selections.json"
    if not selections.exists():
        raise SystemExit("请先运行prepare_compact_schemas.py。")
    sys.path.insert(0, str(SOURCE.parent))
    sys.argv = [str(SOURCE),
        "--subset", str(PROJECT_ROOT/"day10_heldout_evaluation"/"heldout_subset.json"),
        "--schema-selections", str(selections),
        "--schema-source-label", "compact serialization of the complete SQLite schema",
        "--experiment-name", "Compact complete-schema representation validation",
        "--output", str(DAY_DIR/"compact_validation_results.json"), *sys.argv[1:]]
    runpy.run_path(str(SOURCE), run_name="__main__")

if __name__ == "__main__": main()

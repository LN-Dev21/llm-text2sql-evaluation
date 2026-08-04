"""在150题held-out子集上运行完整Schema基线。"""

from __future__ import annotations
import runpy, sys
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE = PROJECT_ROOT / "day4_spider_subset" / "run_spider_baseline.py"

def main() -> None:
    sys.path.insert(0, str(SOURCE.parent))
    sys.argv = [str(SOURCE), "--subset", str(DAY_DIR/"heldout_subset.json"),
                "--experiment-name", "Held-out full-schema baseline",
                "--output", str(DAY_DIR/"heldout_full_schema_results.json"), *sys.argv[1:]]
    runpy.run_path(str(SOURCE), run_name="__main__")

if __name__ == "__main__": main()

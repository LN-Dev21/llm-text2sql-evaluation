"""在150题held-out子集上运行冻结的Exp2词法Schema Linking。"""

from __future__ import annotations
import runpy, sys
from pathlib import Path

DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE = PROJECT_ROOT / "day4_spider_subset" / "run_spider_baseline.py"

def main() -> None:
    selections = DAY_DIR/"heldout_lexical_selections.json"
    if not selections.exists():
        raise SystemExit("请先运行audit_heldout_schema_linking.py。")
    sys.path.insert(0, str(SOURCE.parent))
    sys.argv = [str(SOURCE), "--subset", str(DAY_DIR/"heldout_subset.json"),
                "--schema-selections", str(selections),
                "--experiment-name", "Held-out frozen Exp2 lexical schema linking",
                "--output", str(DAY_DIR/"heldout_lexical_results.json"), *sys.argv[1:]]
    runpy.run_path(str(SOURCE), run_name="__main__")

if __name__ == "__main__": main()

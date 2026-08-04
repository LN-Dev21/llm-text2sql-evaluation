"""使用已冻结的Exp2 Top-4配置生成held-out Schema选择并离线审计。"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


DAY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAY_DIR.parent
SOURCE_SCRIPT = PROJECT_ROOT / "day7_lexical_schema_linking" / "audit_lexical_linking.py"


def main() -> None:
    sys.path.insert(0, str(SOURCE_SCRIPT.parent))
    sys.argv = [
        str(SOURCE_SCRIPT), "--subset", str(DAY_DIR / "heldout_subset.json"),
        "--selections", str(DAY_DIR / "heldout_lexical_selections.json"),
        "--audit", str(DAY_DIR / "heldout_lexical_audit.json"), "--top-k", "4",
    ]
    runpy.run_path(str(SOURCE_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()

"""Reset workspace/repo to the pristine target/ checkout.

Run between factory cycles so each demo starts from a known state. The agents mutate
workspace/repo (gitignored); target/ is the tracked pristine copy.

    .venv/bin/python scripts/seed_workspace.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "target"
WORKSPACE = ROOT / "workspace" / "repo"


def main() -> int:
    if not TARGET.is_dir():
        print(f"missing {TARGET}", file=sys.stderr)
        return 2
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    shutil.copytree(TARGET, WORKSPACE, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", "*.pyc"
    ))
    files = sum(1 for _ in WORKSPACE.rglob("*") if _.is_file())
    print(f"seeded {WORKSPACE} from target/ ({files} files)")
    print("the Builder starts here; acceptance/ stays outside its reach")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

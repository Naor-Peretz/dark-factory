"""Print the workspace fingerprint. Agents run this to bind evidence to a tree state.

    python scripts/fingerprint.py          # just the hash
    python scripts/fingerprint.py --files  # hash plus the files it covers
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.build import WORKSPACE  # noqa: E402
from factory.fingerprint import fingerprint, manifest  # noqa: E402

print(f"WORKSPACE-FINGERPRINT: {fingerprint(WORKSPACE)}")
if "--files" in sys.argv:
    for line in manifest(WORKSPACE):
        print(f"  {line}")

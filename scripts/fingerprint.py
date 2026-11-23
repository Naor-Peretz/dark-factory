"""Print a room checkout's fingerprint. Agents run this to bind evidence to a tree.

    python scripts/fingerprint.py <room_id>
    python scripts/fingerprint.py <room_id> --files

A verdict is only as good as the tree it was measured against. The Verifier stamps its
evidence with this hash before its first check and after its last; the Gatekeeper
blocks evidence that is unstamped or whose two readings disagree.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.build import ROOMS  # noqa: E402
from factory.fingerprint import fingerprint, manifest  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    print("usage: fingerprint.py <room_id> [--files]", file=sys.stderr)
    rooms = sorted(p.name for p in ROOMS.iterdir() if p.is_dir()) if ROOMS.is_dir() else []
    print(f"seeded rooms: {rooms or 'none'}", file=sys.stderr)
    raise SystemExit(2)

workspace = ROOMS / args[0]
if not workspace.is_dir():
    print(f"no checkout at {workspace}", file=sys.stderr)
    print(f"seed it first: python scripts/seed_workspace.py {args[0]}", file=sys.stderr)
    raise SystemExit(2)

print(f"WORKSPACE-FINGERPRINT: {fingerprint(workspace)}")
if "--files" in sys.argv:
    for line in manifest(workspace):
        print(f"  {line}")

"""Seed a room's checkout from the pristine target/.

Each BAND room gets its own checkout under workspace/rooms/<room_id>. That isolation
is not cosmetic: an agent joins *every* room it belongs to, and a single shared `cwd`
means a stale room resuming on restart runs a second cycle concurrently with the real
one -- two Builders editing the same files. That happened on 23 Nov and shifted the
workspace fingerprint mid-verification.

    python scripts/seed_workspace.py <room_id>     # seed one room
    python scripts/seed_workspace.py --list        # show seeded rooms

The checkout gets its own git repo with a baseline commit, which is what makes
"the existing suite still passes from a clean checkout" and "do not modify the auth
handler" measurable at all:
    git stash -u && pytest && git stash pop   -> the pristine suite
    git diff HEAD -- app.py                   -> what the Builder actually changed
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "target"
ROOMS = ROOT / "workspace" / "rooms"

IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


def baseline_commit(workspace: Path) -> str | None:
    """Give the checkout a git history with one pristine commit."""
    env = {
        "GIT_AUTHOR_NAME": "factory-baseline",
        "GIT_AUTHOR_EMAIL": "baseline@localhost",
        "GIT_COMMITTER_NAME": "factory-baseline",
        "GIT_COMMITTER_EMAIL": "baseline@localhost",
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    try:
        def run(*a):
            return subprocess.run(
                a, cwd=workspace, env=env, check=True, capture_output=True, text=True
            )

        run("git", "init", "-q", "-b", "main")
        run("git", "add", "-A")
        run("git", "commit", "-q", "-m", "Baseline: auth service before the factory runs")
        return run("git", "rev-parse", "--short", "HEAD").stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        detail = (getattr(e, "stderr", "") or str(e)).strip()[:120]
        print(f"WARNING: no baseline commit ({detail})", file=sys.stderr)
        print("Criteria about a clean checkout or an unmodified handler will be",
              file=sys.stderr)
        print("unprovable, and the Gatekeeper should block them.", file=sys.stderr)
        return None


def seed(room_id: str) -> Path:
    workspace = ROOMS / room_id
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TARGET, workspace, ignore=IGNORE)
    files = sum(1 for p in workspace.rglob("*") if p.is_file())
    print(f"seeded {workspace} ({files} files)")
    if sha := baseline_commit(workspace):
        print(f"baseline commit {sha} -- clean-checkout and handler diffs are checkable")
    return workspace


def main() -> int:
    if not TARGET.is_dir():
        print(f"missing {TARGET}", file=sys.stderr)
        return 2

    if "--list" in sys.argv:
        if not ROOMS.is_dir() or not any(ROOMS.iterdir()):
            print("no rooms seeded yet")
            return 0
        for d in sorted(p for p in ROOMS.iterdir() if p.is_dir()):
            n = sum(1 for p in d.rglob("*") if p.is_file() and ".git" not in p.parts)
            print(f"  {d.name}  ({n} files)")
        return 0

    args = sys.argv[1:]
    if not args:
        print("usage: seed_workspace.py <room_id>", file=sys.stderr)
        print("A room id comes from the Band room URL:", file=sys.stderr)
        print("  https://app.band.ai/rooms/<room_id>", file=sys.stderr)
        return 2

    seed(args[0])
    print("the Builder starts here; acceptance/ stays outside its reach")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

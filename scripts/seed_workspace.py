"""Reset workspace/repo to the pristine target/ checkout.

Run between factory cycles so each demo starts from a known state. The agents mutate
workspace/repo (gitignored); target/ is the tracked pristine copy.

    .venv/bin/python scripts/seed_workspace.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
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

    # Give the checkout its own git history with a pristine baseline commit.
    #
    # Without this the Gatekeeper is right to block two criteria as unmeasurable:
    # "the existing suite still passes from a clean checkout" cannot be demonstrated
    # when there is no checkout to be clean, and "do not modify the auth handler" has
    # no baseline to diff against. A commit makes both checkable:
    #     git stash && pytest && git stash pop     -> the pristine suite
    #     git diff HEAD -- app.py                  -> what the Builder actually changed
    #
    # It is a repo of its own (workspace/ is gitignored by the parent), so the agents
    # can commit freely without touching the project's history.
    env = {
        "GIT_AUTHOR_NAME": "factory-baseline",
        "GIT_AUTHOR_EMAIL": "baseline@localhost",
        "GIT_COMMITTER_NAME": "factory-baseline",
        "GIT_COMMITTER_EMAIL": "baseline@localhost",
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
    }
    try:
        run = lambda *a: subprocess.run(  # noqa: E731
            a, cwd=WORKSPACE, env=env, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q", "-b", "main")
        run("git", "add", "-A")
        run("git", "commit", "-q", "-m", "Baseline: auth service before the factory runs")
        sha = run("git", "rev-parse", "--short", "HEAD").stdout.strip()
        print(f"baseline commit {sha} — 'clean checkout' and handler diffs are now checkable")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        detail = getattr(e, "stderr", "") or str(e)
        print(f"WARNING: no baseline commit ({detail.strip()[:120]})", file=sys.stderr)
        print("criteria about a clean checkout or an unmodified handler will be", file=sys.stderr)
        print("unprovable, and the Gatekeeper should block them.", file=sys.stderr)

    print("the Builder starts here; acceptance/ stays outside its reach")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

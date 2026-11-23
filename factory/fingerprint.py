"""Bind evidence to the state of the world.

A verdict is only as good as the tree it was measured against. Without a binding, a
Verifier can test a tree, the tree can change, and the Gatekeeper rules on a report
describing something that no longer exists.

Observed live on 23 Nov: the workspace was reseeded between the Verifier's run and the
Gatekeeper's verdict. The Gatekeeper shipped a rate limiter that was not there. The
oracle failed 5/10 against the tree that actually existed at verdict time.

The fingerprint is a deterministic hash of the workspace's source files. The Verifier
stamps its evidence with it; the Gatekeeper recomputes and blocks on a mismatch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".band-workspaces", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".log"}


def fingerprint(root: Path) -> str:
    """A short, stable hash of every source file under `root`.

    Deterministic across runs and machines: paths are relative and sorted, content is
    hashed bytewise. Caches and VCS metadata are excluded so a fingerprint reflects the
    code, not the noise around it.
    """
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        h.update(str(rel).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]


def manifest(root: Path) -> list[str]:
    """The files the fingerprint covers, for a human reading the room."""
    out = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        out.append(f"{rel}  {path.stat().st_size}B")
    return out

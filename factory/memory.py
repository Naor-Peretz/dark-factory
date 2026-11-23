"""The factory's memory across cycles, backed by cognee.

Why this exists: Band's `Capability.MEMORY` is Enterprise-only, so the crew starts every
run cold. A finding from yesterday is gone, and the factory can repeat a mistake it has
already made and already fixed. That is the gap cognee fills here.

Two deliberate design choices:

1. **Agents call a CLI, they do not import cognee.** The dependency is heavy (torch,
   lancedb, litellm) and cognee loads `.env` with overwrite=True at import, which would
   clobber the Band configuration inside an agent process. A short-lived subprocess
   contains both problems, and the coding agents already have a shell.

2. **One writer at a time, enforced by a file lock.** cognee's default embedded graph is
   documented as "not suitable for concurrent use from different agents or processes"
   -- and four separate agent processes is exactly that. The alternative is running a
   cognee server; a lock is far less machinery for a crew this size, and the factory's
   memory writes are rare (a handful per cycle) so contention is negligible.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEMORY_ROOT = REPO_ROOT / "workspace" / "memory"
LOCK_PATH = MEMORY_ROOT / ".writer.lock"

# cognee resolves its default roots *inside the venv* unless told otherwise, which makes
# a store look empty when anything about the environment shifts. Pin them absolutely.
SYSTEM_DIR = MEMORY_ROOT / "system"
DATA_DIR = MEMORY_ROOT / "data"

DATASET = "dark_factory_lessons"


@dataclass
class Lesson:
    """One thing the factory learned, written after a cycle ends."""

    spec_id: str
    role: str
    text: str

    def render(self) -> str:
        """Store a self-describing sentence: recall returns text, not structure."""
        return f"[spec:{self.spec_id}] [role:{self.role}] {self.text.strip()}"


@contextmanager
def writer_lock(timeout_s: float = 60.0):
    """Serialize access to the embedded store across processes.

    cognee's default graph engine takes a file lock of its own and errors with
    "Could not set lock on file" under concurrent churn. Holding our own lock around
    the whole operation turns a crash into a short wait.
    """
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.touch(exist_ok=True)
    with open(LOCK_PATH, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def configure_env() -> None:
    """Point cognee at our directories before it is imported."""
    SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(SYSTEM_DIR))
    os.environ.setdefault("DATA_ROOT_DIRECTORY", str(DATA_DIR))
    # Keep telemetry off by default; this is someone's machine.
    os.environ.setdefault("TELEMETRY_DISABLED", "1")

"""Spec loading. The spec is an input file so the real challenge is a drop-in."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"


@dataclass
class Spec:
    id: str
    rev: int
    text: str
    path: Path

    @property
    def criteria(self) -> list[str]:
        """Acceptance criteria, parsed from a '## Acceptance criteria' list."""
        m = re.search(
            r"^##+\s*Acceptance criteria\s*$(.*?)(?=^##\s|\Z)",
            self.text,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if not m:
            return []
        return [
            line.group(1).strip()
            for line in re.finditer(r"^\s*(?:[-*]|\d+\.)\s+(.*)$", m.group(1), re.MULTILINE)
        ]


def load(spec_id: str | None = None, *, spec_dir: Path | None = None) -> Spec:
    d = spec_dir or SPEC_DIR
    candidates = sorted(d.glob("*.md"))
    if not candidates:
        raise FileNotFoundError(f"no spec in {d}/ -- drop the challenge in as a .md file")
    if spec_id:
        match = [p for p in candidates if p.stem == spec_id]
        if not match:
            raise FileNotFoundError(f"spec {spec_id!r} not in {d}/")
        path = match[0]
    elif len(candidates) > 1:
        raise ValueError(f"several specs in {d}/, pass spec_id: {[p.stem for p in candidates]}")
    else:
        path = candidates[0]
    text = path.read_text()
    rev = int(m.group(1)) if (m := re.search(r"^rev:\s*(\d+)", text, re.MULTILINE)) else 1
    return Spec(id=path.stem, rev=rev, text=text, path=path)

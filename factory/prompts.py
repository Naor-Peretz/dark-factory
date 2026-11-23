"""Prompt assembly. Every role gets the shared protocol plus its own mandate."""

from __future__ import annotations

from pathlib import Path

from .roles import Role

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def build(role: Role, *, spec_text: str | None = None) -> str:
    common = (PROMPT_DIR / "_common.md").read_text()
    own = (PROMPT_DIR / role.prompt).read_text()
    if role.key == "verifier":
        acceptance = PROMPT_DIR.parent / "acceptance"
        own = own.replace("$ACCEPTANCE_DIR", str(acceptance))
        own += f"\n\nACCEPTANCE_DIR = {acceptance}\n"
    parts = [common, "", "---", "", own]
    if spec_text:
        parts += ["", "---", "", "# Current spec", "", spec_text]
    return "\n".join(parts)

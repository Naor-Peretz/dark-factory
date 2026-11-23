"""Prompt assembly. Every role gets the shared protocol plus its own mandate."""

from __future__ import annotations

from pathlib import Path

from .roles import Role

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def build(role: Role, *, spec_text: str | None = None) -> str:
    common = (PROMPT_DIR / "_common.md").read_text()
    own = (PROMPT_DIR / role.prompt).read_text()
    root = PROMPT_DIR.parent
    if role.key == "verifier":
        acceptance = root / "acceptance"
        own = own.replace("$ACCEPTANCE_DIR", str(acceptance))
        own += f"\n\nACCEPTANCE_DIR = {acceptance}\n"
    own = own.replace("$FINGERPRINT_CMD", str(root / "scripts" / "fingerprint.py"))
    # Absolute interpreter AND script. With a bare `python` the Architect spent three
    # turns hunting for the venv and then gave up without calling memory at all.
    memory_cmd = f"{root / '.venv' / 'bin' / 'python'} {root / 'scripts' / 'memory.py'}"
    own = own.replace("$MEMORY_CMD", memory_cmd)
    parts = [common, "", "---", "", own]
    if spec_text:
        parts += ["", "---", "", "# Current spec", "", spec_text]
    return "\n".join(parts)

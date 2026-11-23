"""Adapter construction per role.

All four roles default to ClaudeSDKAdapter because it authenticates off the local
`claude login` subscription -- no API key, no per-token cost. The Verifier's adapter is
swappable via VERIFIER_ADAPTER so we can give it a different model family later (the
cross-family critic is a judging criterion), without touching anything else.

Verified against band-sdk 9.3.0 by introspection:
  ClaudeSDKAdapter(config=None, *, history_converter, additional_tools,
                   workspace_for_room, **features)
Config fields go in ClaudeSDKAdapterConfig. emit/capabilities are **features kwargs.
Passing config fields as kwargs raises TypeError.
"""

from __future__ import annotations

import os
from pathlib import Path

from band import Emit

from .roles import Role

REPO_ROOT = Path(__file__).resolve().parent.parent
# Deliberately NOT the project root: a coding agent's cwd must never contain
# agent_config.yaml, or Claude Code can read the API key and a tool result can
# post it into the room.
WORKSPACE = REPO_ROOT / "workspace" / "repo"
# The Verifier's independent oracle. Deliberately OUTSIDE the Builder's cwd: a critic
# that can read the author's tests is not an independent check, and one that can edit
# them is no check at all. Supplied to the Verifier alone via the CLI's add_dirs.
ACCEPTANCE = REPO_ROOT / "acceptance"

EMIT_ALL = (Emit.TOOL_CALLS, Emit.THOUGHTS, Emit.USAGE)


def adapter_for(role: Role, prompt: str):
    """Build the adapter for a role. Keep execution events ON -- the room transcript
    is part of the submission, and tool calls are what make the handoffs legible."""
    kind = os.environ.get("VERIFIER_ADAPTER", "claude") if role.key == "verifier" else "claude"

    if kind == "claude":
        from band.adapters import ClaudeSDKAdapter, ClaudeSDKAdapterConfig

        cfg: dict = {"custom_section": prompt, "turn_timeout_s": 600.0}
        if role.writes_code:
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            cfg["cwd"] = WORKSPACE
            cfg["permission_mode"] = "acceptEdits"
        else:
            # Real enforcement, not just prompt discipline: plan mode cannot edit files.
            cfg["permission_mode"] = "plan"
        if role.key == "verifier":
            from band.adapters.claude_sdk import ClaudeCLIOptions

            cfg["cli"] = ClaudeCLIOptions(add_dirs=(str(ACCEPTANCE),))
        return ClaudeSDKAdapter(ClaudeSDKAdapterConfig(**cfg), emit=EMIT_ALL)

    if kind == "codex":
        from band.adapters import CodexAdapter, CodexAdapterConfig

        WORKSPACE.mkdir(parents=True, exist_ok=True)
        return CodexAdapter(
            CodexAdapterConfig(
                custom_section=prompt,
                cwd=str(WORKSPACE),
                model=os.environ.get("VERIFIER_MODEL", "gpt-5.5"),
                reasoning_effort=os.environ.get("VERIFIER_EFFORT", "high"),
                approval_mode="auto_accept",
            ),
            emit=EMIT_ALL,
        )

    if kind == "gemini":
        from band.adapters import GeminiAdapter, GeminiAdapterConfig

        return GeminiAdapter(
            GeminiAdapterConfig(
                custom_section=prompt,
                model=os.environ.get("VERIFIER_MODEL", "gemini-2.5-pro"),
            ),
            emit=EMIT_ALL,
        )

    raise SystemExit(f"unknown VERIFIER_ADAPTER={kind!r} (claude|codex|gemini)")

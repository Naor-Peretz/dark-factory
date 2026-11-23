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


# Roles that must actually execute things: run pytest, edit files, diff against a
# baseline. Only a coding-agent adapter can serve these. A plain LLM adapter cannot.
EXECUTING = {"builder", "verifier"}

# Adapters that give the agent a shell and a filesystem.
CODING_ADAPTERS = {"claude", "codex"}


def adapter_kind(role: Role) -> str:
    """Which adapter backs this role: ADAPTER_<ROLE> env var, else claude.

    Every role defaults to ClaudeSDKAdapter, which authenticates off the local
    `claude login` subscription -- no API key, no per-token cost.

    Swapping one role to another model family is a judging criterion (the critic should
    not be the author's own judgment) and also relieves a single subscription carrying
    four concurrent agents. The natural candidate is the **Gatekeeper**: it only reads
    evidence and rules, so it needs no tools at all.
    """
    kind = os.environ.get(f"ADAPTER_{role.key.upper()}", "claude").lower()
    if role.key in EXECUTING and kind not in CODING_ADAPTERS:
        raise SystemExit(
            f"ADAPTER_{role.key.upper()}={kind!r} cannot work: the {role.name} must run "
            f"commands (pytest, git diff), and {kind!r} is a plain LLM adapter with no "
            f"shell or filesystem. Use one of {sorted(CODING_ADAPTERS)}, or move the "
            f"cross-family model to the Gatekeeper, which only reads evidence."
        )
    return kind


def adapter_for(role: Role, prompt: str):
    """Build the adapter for a role. Keep execution events ON -- the room transcript
    is part of the submission, and tool calls are what make the handoffs legible."""
    kind = adapter_kind(role)

    if kind == "claude":
        from band.adapters import ClaudeSDKAdapter, ClaudeSDKAdapterConfig

        cfg: dict = {"custom_section": prompt, "turn_timeout_s": 600.0}
        # permission_mode is acceptEdits for EVERY role. Do not use "plan" here:
        # plan mode blocks every tool call, band_send_message included, so a planning
        # agent composes a perfect handoff and then cannot send it. Observed live on
        # 23 Nov: "Cannot call mcp__band__band_send_message while in plan mode."
        cfg["permission_mode"] = "acceptEdits"
        if role.writes_code:
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            cfg["cwd"] = WORKSPACE
            # acceptEdits covers file writes but NOT shell commands, so every
            # `pytest` was refused with "This command requires approval" -- and an
            # unattended agent has nobody to approve it. Observed live on 23 Nov: the
            # Verifier correctly refused to pass work it could not test, and the whole
            # factory stalled. Only the two roles that must execute things get this.
            from band.adapters.claude_sdk import ClaudeApprovalOptions, ClaudeCLIOptions

            # Put the project venv first on PATH. Without it `python -m pytest` finds a
            # system interpreter with no flask installed. The Verifier recovered on its
            # own (tried python3, then located .venv) but burned three turns doing it.
            env = {
                "PATH": f"{REPO_ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}",
                "VIRTUAL_ENV": str(REPO_ROOT / ".venv"),
            }
            cli_kw: dict = {"env": env}
            if role.key == "verifier":
                cli_kw["add_dirs"] = (str(ACCEPTANCE),)
            cfg["cli"] = ClaudeCLIOptions(**cli_kw)

            cfg["approvals"] = ClaudeApprovalOptions(
                mode="auto_accept",
                wait_timeout_s=120.0,       # below turn_timeout_s; waits count toward it
                timeout_decision="decline",
                # CRITICAL. With the default True, every auto-accepted approval is ALSO
                # posted into the room as "Approval requested (Bash: ...)" addressed to
                # another agent. That agent reasonably answers "I can't approve that",
                # which re-triggers the first -- a two-agent loop that produced 7
                # consecutive band_no_reply turns and burned real money on 23 Nov
                # before it was killed. Auto-accepted approvals need no audience.
                text_notifications=False,
            )
        # Non-coding roles get NO cwd, so the adapter gives each its own empty
        # .band-workspaces/<room_id>. That is the real boundary: the Architect and
        # Gatekeeper cannot reach the Builder's checkout because it is not theirs,
        # not because their tools are switched off.
        return ClaudeSDKAdapter(ClaudeSDKAdapterConfig(**cfg), emit=EMIT_ALL)

    if kind == "codex":
        from band.adapters import CodexAdapter, CodexAdapterConfig

        WORKSPACE.mkdir(parents=True, exist_ok=True)
        return CodexAdapter(
            CodexAdapterConfig(
                custom_section=prompt,
                cwd=str(WORKSPACE),
                model=_model_for(role, "gpt-5.5"),
                reasoning_effort=os.environ.get(f"EFFORT_{role.key.upper()}", "high"),
                approval_mode="auto_accept",
            ),
            emit=EMIT_ALL,
        )

    if kind == "gemini":
        # A plain LLM adapter: no shell, no filesystem. Fine for the Gatekeeper, which
        # rules on evidence in the room and needs no tools; refused above for the
        # Builder and Verifier, which must execute things.
        #
        # Reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment.
        from band.adapters import GeminiAdapter, GeminiAdapterConfig

        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise SystemExit(
                f"ADAPTER_{role.key.upper()}=gemini needs GEMINI_API_KEY in .env "
                f"(free tier at https://aistudio.google.com)"
            )
        gcfg: dict = {"custom_section": prompt}
        if override := _model_for(role, None):
            gcfg["model"] = override  # else keep the adapter's own default
        return GeminiAdapter(GeminiAdapterConfig(**gcfg), emit=EMIT_ALL)

    raise SystemExit(
        f"unknown ADAPTER_{role.key.upper()}={kind!r} (claude|codex|gemini)"
    )


def _model_for(role: Role, default: str | None) -> str | None:
    """MODEL_<ROLE> overrides; otherwise the adapter's own default."""
    return os.environ.get(f"MODEL_{role.key.upper()}") or default

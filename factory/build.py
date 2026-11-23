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

from band import Emit, create_room_workspace_resolver

from .roles import Role

REPO_ROOT = Path(__file__).resolve().parent.parent
# Deliberately NOT the project root: a coding agent's cwd must never contain
# agent_config.yaml, or Claude Code can read the API key and a tool result can
# post it into the room.
WORKSPACE = REPO_ROOT / "workspace" / "repo"
# One checkout per room, under here. Setting `cwd` instead shares a SINGLE checkout
# across every room the agent belongs to -- and an agent joins all of them. Observed
# live on 23 Nov: a stale room resumed on restart and ran a second cycle concurrently
# with the real one, two Builders editing the same files, and the fingerprint shifted
# mid-run. `cwd` and `workspace_for_room` are mutually exclusive; prefer the latter.
ROOMS = REPO_ROOT / "workspace" / "rooms"
# The Verifier's independent oracle. Deliberately OUTSIDE the Builder's cwd: a critic
# that can read the author's tests is not an independent check, and one that can edit
# them is no check at all. Supplied to the Verifier alone via the CLI's add_dirs.
ACCEPTANCE = REPO_ROOT / "acceptance"

# Execution events stay ON: the room transcript is part of the submission, and visible
# tool calls are what make a handoff legible to someone reading it afterwards.
#
# Adapters differ in what they can emit, and passing an unsupported kind is a hard
# BandConfigError at construction, not a warning. GeminiAdapter has no thoughts stream.
EMIT_ALL = (Emit.TOOL_CALLS, Emit.THOUGHTS, Emit.USAGE)
EMIT_BY_ADAPTER = {
    "claude": EMIT_ALL,
    "codex": EMIT_ALL,
    "gemini": (Emit.TOOL_CALLS, Emit.USAGE),  # no THOUGHTS: unsupported
}


# Roles that must actually execute things: run pytest, edit files, diff against a
# baseline. Only a coding-agent adapter can serve these. A plain LLM adapter cannot.
EXECUTING = {"builder", "verifier"}

# Roles that need an unattended shell. Wider than EXECUTING because the Architect runs
# the memory CLI: it recalls what earlier cycles learned before planning, and records
# the lesson when a verdict closes the loop back to it. It still gets no checkout, so
# a shell buys it memory, not the ability to edit code.
NEEDS_SHELL = EXECUTING | {"architect"}

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
        if role.key in NEEDS_SHELL and not role.writes_code:
            # The Architect: a shell for the memory CLI, but no checkout. It recalls
            # what earlier cycles learned before planning, and records the lesson when
            # a verdict closes the loop back to it. acceptEdits does not cover shell
            # commands, so without approvals every memory call would hang waiting for
            # a human who is not there.
            from band.adapters.claude_sdk import ClaudeApprovalOptions, ClaudeCLIOptions

            cfg["cli"] = ClaudeCLIOptions(
                add_dirs=(str(REPO_ROOT / "scripts"), str(REPO_ROOT / "factory")),
                env={
                    "PATH": f"{REPO_ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}",
                    "VIRTUAL_ENV": str(REPO_ROOT / ".venv"),
                },
            )
            cfg["approvals"] = ClaudeApprovalOptions(
                mode="auto_accept", wait_timeout_s=120.0,
                timeout_decision="decline", text_notifications=False,
            )
        if role.writes_code:
            ROOMS.mkdir(parents=True, exist_ok=True)
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
        # Non-coding roles get neither cwd nor a resolver, so the adapter gives each
        # its own empty .band-workspaces/<room_id>. That is the real boundary: the
        # Architect and Gatekeeper cannot reach the Builder's checkout because it is
        # not theirs, not because their tools are switched off.
        resolver = create_room_workspace_resolver(ROOMS) if role.writes_code else None
        return ClaudeSDKAdapter(
            ClaudeSDKAdapterConfig(**cfg),
            workspace_for_room=resolver,
            emit=EMIT_ALL,
        )

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
        # The free tier returns 503 UNAVAILABLE ("this model is currently
        # experiencing high demand") under load, and the adapter's default 2 retries
        # are not enough -- observed 23 Nov. These are transient spikes, so back off
        # harder rather than failing a verdict. If Gemini is unusable during a demo,
        # ADAPTER_GATEKEEPER=claude restores a working factory in one variable; the
        # cost is only the cross-family claim.
        gcfg: dict = {
            "custom_section": prompt,
            "max_retries": int(os.environ.get("GEMINI_MAX_RETRIES", "6")),
            "retry_base_delay_s": float(os.environ.get("GEMINI_RETRY_DELAY", "2.0")),
        }
        if override := _model_for(role, None):
            gcfg["model"] = override  # else keep the adapter's own default
        return GeminiAdapter(GeminiAdapterConfig(**gcfg), emit=EMIT_BY_ADAPTER["gemini"])

    raise SystemExit(
        f"unknown ADAPTER_{role.key.upper()}={kind!r} (claude|codex|gemini)"
    )


def _model_for(role: Role, default: str | None) -> str | None:
    """MODEL_<ROLE> overrides; otherwise the adapter's own default."""
    return os.environ.get(f"MODEL_{role.key.upper()}") or default

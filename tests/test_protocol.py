"""Protocol tests. These run with no BAND account, no room, and no model key.

They prove the two properties the factory is judged on:
  * a handoff is *dependent* -- the receiver gets the specific finding, not the task
  * a verdict is *blockable* -- the Gatekeeper's BLOCKED routes back and nothing ships
and the one property that makes it not fall over: context survives every hop.
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from band.testing import FakeAgentTools  # noqa: E402

from factory.handoff import Finding, Handoff  # noqa: E402
from factory.roles import BUILDER, GATEKEEPER, ROLES, VERIFIER  # noqa: E402
from factory.spec import Spec  # noqa: E402

CRITERIA = [
    "the 11th request within 60s returns 429",
    "the limiter resets after the window elapses",
    "a 429 response carries a Retry-After header",
]

def _agent(pid: str, name: str, handle: str, role: str = "member") -> dict:
    return {
        "id": pid,
        "name": name,
        "handle": handle,
        "role": role,
        "status": "active",
        "type": "Agent",
    }


def _peer(pid: str, name: str, handle: str, description: str = "") -> dict:
    """A discoverable peer. Distinct schema from ChatParticipant."""
    return {
        "id": pid,
        "name": name,
        "handle": handle,
        "description": description,
        "is_contact": False,
        "online": True,
        "source": "registry",
        "type": "Agent",
    }


PARTICIPANTS = [
    _agent("a-1", "Architect", "architect", role="owner"),
    _agent("a-2", "Builder", "builder"),
    _agent("a-3", "Verifier", "verifier"),
    _agent("a-4", "Gatekeeper", "gatekeeper"),
]


def plan() -> Handoff:
    return Handoff(
        spec_id="auth-rate-limit",
        spec_rev=1,
        stage="plan",
        sender="Architect",
        body="Add a token-bucket limiter in middleware. Do not touch the auth handler.",
        criteria=list(CRITERIA),
    )


# --- the envelope survives the room round-trip -------------------------------


def test_envelope_round_trips_through_room_text():
    rendered = plan().render("Builder")
    back = Handoff.parse(rendered)
    assert back is not None
    assert back.spec_id == "auth-rate-limit"
    assert back.spec_rev == 1
    assert back.stage == "plan"
    assert back.sender == "Architect"
    assert back.criteria == CRITERIA, "criteria must survive verbatim"
    assert "token-bucket" in back.body


def test_parse_returns_none_on_unstructured_chatter():
    assert Handoff.parse("@Builder looks good to me, ship it") is None


def test_forward_cannot_silently_drop_context():
    """The whole reason the envelope exists: a mention carries no context."""
    h = plan().forward("Builder", "build", "Implemented the limiter.")
    assert h.criteria == CRITERIA, "forwarding must preserve acceptance criteria"
    assert h.spec_id == "auth-rate-limit"
    assert h.spec_rev == 1


def test_open_findings_are_carried_and_resolution_is_explicit():
    f1 = Finding("F-1", "VERIFIER", "429 missing Retry-After header")
    f2 = Finding("F-2", "VERIFIER", "limiter never resets")
    handed_back = plan().forward("Verifier", "verify", "Two criteria fail.", findings=[f1, f2])
    assert len(handed_back.open_findings) == 2

    f1.resolved = True
    onward = handed_back.forward("Builder", "build", "Fixed the header.")
    assert [f.id for f in onward.open_findings] == ["F-2"], "resolved findings drop out, open ones persist"
    assert len(onward.findings) == 2, "but the full history is retained"


# --- the dependent handoff ---------------------------------------------------


@pytest.mark.asyncio
async def test_verifier_failure_routes_the_finding_to_builder_not_the_task():
    """A dependent handoff: Builder receives the specific defect, not the spec again."""
    tools = FakeAgentTools(participants=PARTICIPANTS, agent_id="a-3")

    finding = Finding(
        "F-1",
        "VERIFIER",
        "test_rate_limit_resets fails: expected 429 on request 11, got 200",
    )
    out = plan().forward(
        "Verifier",
        "verify",
        "Criterion 2 fails.",
        findings=[finding],
        evidence="$ pytest tests/test_limit.py -- exit 1\nE  assert 200 == 429",
    )
    await tools.send_message(out.render(VERIFIER.on_reject), mentions=[VERIFIER.on_reject])

    tools.assert_message_sent(mentions=["Builder"], count=1)
    sent = tools.messages_sent[0]["content"]
    assert "Prior findings (must be answered)" in sent
    assert "[VERIFIER/F-1]" in sent
    assert "expected 429 on request 11, got 200" in sent
    assert "exit 1" in sent, "evidence travels with the finding"
    # and the criteria are still there, so Builder needs nothing else
    assert all(c in sent for c in CRITERIA)


@pytest.mark.asyncio
async def test_verifier_never_routes_a_failure_to_the_gatekeeper():
    """Failures must not reach the ship decision. Topology enforces it."""
    assert VERIFIER.on_reject == "Builder"
    assert VERIFIER.forward_to == "Gatekeeper"
    assert VERIFIER.on_reject != VERIFIER.forward_to


# --- the blockable verdict ---------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_verdict_routes_back_and_does_not_ship():
    tools = FakeAgentTools(participants=PARTICIPANTS, agent_id="a-4")
    verdict = plan().forward(
        "Gatekeeper",
        "blocked",
        "BLOCKED\n\n- [GATEKEEPER/F-3] criterion 3 has no test output; absence of evidence is not evidence.",
    )
    await tools.send_message(verdict.render(GATEKEEPER.on_reject), mentions=[GATEKEEPER.on_reject])

    tools.assert_message_sent(mentions=["Architect"], count=1)
    body = tools.messages_sent[0]["content"]
    assert body.lstrip().startswith("@Architect")
    assert "BLOCKED" in body
    assert "SHIP" not in body


@pytest.mark.asyncio
async def test_runtime_recruit_adds_a_specialist_and_carries_full_context():
    """A roster decided at runtime -- and the new agent has no history, so the
    mention must carry everything."""
    tools = FakeAgentTools(
        participants=PARTICIPANTS,
        peers=[_peer("a-9", "Crypto Reviewer", "crypto", "Reviews token signing and crypto paths.")],
        agent_id="a-1",
    )
    peers = await tools.lookup_peers()
    assert peers.data, "a specialist is discoverable"

    await tools.add_participant("a-9")
    assert any(p.id == "a-9" for p in await tools.get_participants())

    onboarding = plan().forward("Architect", "plan", "Recruited for the token signing path.")
    await tools.send_message(onboarding.render("Crypto Reviewer"), mentions=["Crypto Reviewer"])
    sent = tools.messages_sent[0]["content"]
    assert all(c in sent for c in CRITERIA), "a newly added agent has no history"


# --- turn discipline ---------------------------------------------------------


@pytest.mark.asyncio
async def test_no_reply_is_a_valid_turn_ending():
    """Rule 1: a turn must end in a tool call. no_reply is the legitimate decline."""
    tools = FakeAgentTools(participants=PARTICIPANTS, agent_id="a-2")
    await tools.no_reply(reason="nothing addressed to me")
    tools.assert_no_messages_sent()


@pytest.mark.asyncio
async def test_every_handoff_message_carries_a_mention():
    """Rule: a message with no delivery mention is rejected by BAND."""
    tools = FakeAgentTools(participants=PARTICIPANTS, agent_id="a-1")
    for role in ROLES.values():
        rendered = plan().render(role.forward_to)
        assert rendered.lstrip().startswith(f"@{role.forward_to}")
        await tools.send_message(rendered, mentions=[role.forward_to])
    assert len(tools.messages_sent) == len(ROLES)
    assert all(m["mentions"] for m in tools.messages_sent)


# --- spec parsing ------------------------------------------------------------


def test_spec_criteria_parse_from_markdown():
    s = Spec(
        id="demo",
        rev=2,
        path=Path("spec/demo.md"),
        text=(
            "rev: 2\n\n# Demo\n\nSome prose.\n\n"
            "## Acceptance criteria\n"
            "- the 11th request within 60s returns 429\n"
            "- the limiter resets after the window elapses\n\n"
            "## Notes\n- not a criterion\n"
        ),
    )
    assert s.criteria == [
        "the 11th request within 60s returns 429",
        "the limiter resets after the window elapses",
    ]


def test_spec_with_no_criteria_section_is_empty_not_an_error():
    s = Spec(id="d", rev=1, path=Path("x"), text="# Just prose\n\nno criteria here")
    assert s.criteria == []


# --- the independent oracle --------------------------------------------------


def test_only_the_verifier_can_reach_the_acceptance_oracle():
    """A critic that reads the author's tests is not an independent check.
    A critic that can edit them is no check at all."""
    from factory import build as build_mod
    from factory.roles import ARCHITECT, GATEKEEPER

    acceptance = str(build_mod.ACCEPTANCE)
    verifier_prompt = __import__("factory.prompts", fromlist=["build"]).build(VERIFIER)
    assert acceptance in verifier_prompt, "the Verifier must know where its oracle is"

    for role in (BUILDER, ARCHITECT, GATEKEEPER):
        other = __import__("factory.prompts", fromlist=["build"]).build(role)
        assert acceptance not in other, f"{role.name} must not learn the oracle's path"


def test_acceptance_oracle_lives_outside_every_room_checkout():
    from factory.build import ACCEPTANCE, ROOMS

    assert ACCEPTANCE.exists(), "the oracle must exist"
    assert ROOMS not in ACCEPTANCE.parents and ACCEPTANCE != ROOMS, (
        "the oracle must sit outside the room checkouts, or a Builder could edit it"
    )


def test_verifier_prompt_warns_about_the_vacuous_pass():
    """Before a feature exists, several oracle tests pass for the wrong reason.
    A rising pass count is not progress, and the Verifier must know that."""
    prompt = __import__("factory.prompts", fromlist=["build"]).build(VERIFIER)
    assert "vacuous" in prompt.lower()


# --- permission modes --------------------------------------------------------


def test_no_role_runs_in_plan_mode():
    """Regression, found in the first live run.

    `permission_mode="plan"` looks like the natural way to stop the Architect and
    Gatekeeper editing code. It is not: plan mode blocks EVERY tool call, including
    band_send_message, so the agent composes a flawless handoff and then cannot send
    it. The room reported:
        "Cannot call mcp__band__band_send_message while in plan mode."
    followed by a turn that ended without a reply. Enforce the boundary with workspace
    isolation instead, which is what test_non_coding_roles_get_no_repo_access checks.
    """
    from factory import build as build_mod
    from factory.roles import ROLES

    for role in ROLES.values():
        cfg = build_mod.adapter_for(role, "prompt").config
        mode = getattr(cfg.permission_mode, "value", cfg.permission_mode)
        assert mode != "plan", f"{role.name} is in plan mode and cannot speak in the room"


def test_non_coding_roles_get_no_repo_access():
    """Architect and Gatekeeper must not be able to reach the Builder's checkout."""
    from factory import build as build_mod
    from factory.roles import ARCHITECT, BUILDER, GATEKEEPER, VERIFIER

    import shutil

    for role in (ARCHITECT, GATEKEEPER):
        adapter = build_mod.adapter_for(role, "prompt")
        cfg = adapter.config
        assert adapter._workspaces._resolver is None, (
            f"{role.name} must get no room checkout at all"
        )
        assert cfg.cwd is None, (
            f"{role.name} must have no cwd, so the adapter gives it an isolated "
            f"per-room workspace instead of the repo"
        )
        assert not getattr(cfg.cli, "add_dirs", ()), f"{role.name} must get no extra dirs"

    for role in (BUILDER, VERIFIER):
        adapter = build_mod.adapter_for(role, "prompt")
        cfg = adapter.config
        assert cfg.cwd is None, (
            f"{role.name} must use a per-room resolver, not a shared cwd: one cwd is "
            f"shared across every room the agent joins, so two rooms collide"
        )
        resolver = adapter._workspaces._resolver
        assert resolver is not None, f"{role.name} needs a per-room workspace resolver"
        path = pathlib.Path(resolver("room-test"))
        assert path.parent == build_mod.ROOMS and path.name == "room-test", (
            f"{role.name} must resolve into workspace/rooms/<room_id>, got {path}"
        )
        shutil.rmtree(path, ignore_errors=True)


def test_executing_roles_can_run_commands_unattended():
    """Regression from the second live run.

    `acceptEdits` auto-approves file writes but NOT shell commands, so every pytest
    call came back "This command requires approval" -- and an unattended agent has
    nobody to approve it. The Verifier behaved correctly (it refused to pass work it
    could not test) and the factory stalled, which is the right failure but still a
    stall. Roles that must execute things need auto_accept.
    """
    from factory import build as build_mod
    from factory.roles import ARCHITECT, BUILDER, GATEKEEPER, VERIFIER

    for role in (BUILDER, VERIFIER):
        cfg = build_mod.adapter_for(role, "prompt").config
        assert cfg.approvals is not None, f"{role.name} must be able to run commands"
        assert cfg.approvals.mode == "auto_accept"
        assert cfg.approvals.wait_timeout_s < cfg.turn_timeout_s, (
            "an approval wait counts toward the turn timeout, so it must be shorter"
        )

    for role in (ARCHITECT, GATEKEEPER):
        cfg = build_mod.adapter_for(role, "prompt").config
        assert cfg.approvals is None, (
            f"{role.name} does not execute anything; it should not auto-approve"
        )


def test_auto_accepted_approvals_are_not_announced_in_the_room():
    """Regression from the third live run: the approval-notification loop.

    auto_accept still posts "Approval requested (Bash: ...)" into the room by default,
    addressed to another agent. That agent answers "I can't approve that", which
    re-triggers the first. Observed: a Builder/Architect ping-pong, 7 consecutive
    band_no_reply turns, and no progress. An approval that is auto-accepted has no
    audience and must stay silent.
    """
    from factory import build as build_mod
    from factory.roles import BUILDER, VERIFIER

    for role in (BUILDER, VERIFIER):
        cfg = build_mod.adapter_for(role, "prompt").config
        assert cfg.approvals.text_notifications is False, (
            f"{role.name} would announce every auto-accepted approval into the room"
        )


# --- binding evidence to a tree ----------------------------------------------


def test_fingerprint_is_deterministic_and_content_sensitive(tmp_path):
    """A verdict is only as good as the tree it was measured against."""
    from factory.fingerprint import fingerprint

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("y = 2\n")

    first = fingerprint(tmp_path)
    assert first == fingerprint(tmp_path), "same tree must hash the same"

    (tmp_path / "sub" / "b.py").write_text("y = 3\n")
    assert fingerprint(tmp_path) != first, "a content change must change the hash"


def test_fingerprint_ignores_caches_but_not_source(tmp_path):
    from factory.fingerprint import fingerprint

    (tmp_path / "a.py").write_text("x = 1\n")
    base = fingerprint(tmp_path)

    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00junk")
    (tmp_path / "run.log").write_text("noise")
    assert fingerprint(tmp_path) == base, "caches and logs must not shift the hash"

    (tmp_path / "c.py").write_text("z = 9\n")
    assert fingerprint(tmp_path) != base, "a new source file must shift it"


def test_verifier_is_told_to_stamp_before_and_after():
    """One reading proves nothing: the tree can move during the run."""
    from factory import prompts
    from factory.roles import VERIFIER

    p = prompts.build(VERIFIER)
    assert "scripts/fingerprint.py" in p, "the Verifier needs the actual command"
    assert "$FINGERPRINT_CMD" not in p, "placeholder must be substituted"
    assert "WORKSPACE-FINGERPRINT" in p
    low = p.lower()
    assert "before your first check" in low and "after your last" in low


def test_gatekeeper_must_block_unstamped_evidence():
    from factory import prompts
    from factory.roles import GATEKEEPER

    p = prompts.build(GATEKEEPER)
    assert "WORKSPACE-FINGERPRINT" in p
    assert "No fingerprint at all" in p
    assert "readings differ" in p


def test_seeded_workspace_has_a_baseline_commit(tmp_path):
    """Two criteria are unmeasurable without one, and the Gatekeeper blocks them.

    "the existing suite still passes from a clean checkout" needs a checkout to be
    clean; "do not modify the auth handler" needs a baseline to diff against. The
    Gatekeeper blocked both on 23 Nov, correctly, because workspace/repo had no git
    history at all.
    """
    import subprocess
    import sys

    from factory.build import REPO_ROOT, ROOMS

    room = "test-room-baseline"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "seed_workspace.py"), room],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    ws = ROOMS / room
    try:
        assert (ws / ".git").is_dir(), "seeding must create a git baseline"
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=ws, capture_output=True, text=True
        )
        assert log.returncode == 0 and log.stdout.strip(), "baseline commit missing"
        assert (ws / "app.py").is_file(), "the target must be copied in"
    finally:
        import shutil
        shutil.rmtree(ws, ignore_errors=True)


def test_verifier_knows_how_to_prove_clean_checkout_and_no_diff():
    from factory import prompts
    from factory.roles import VERIFIER

    p = prompts.build(VERIFIER)
    assert "git stash" in p, "the Verifier needs the clean-checkout recipe"
    assert "git diff HEAD" in p, "the Verifier needs the baseline-diff recipe"
    assert "Summaries are not evidence" in p, "raw output must be mandatory"


def test_fingerprint_ignores_git_metadata(tmp_path):
    """A baseline commit must not shift the hash, or every seed looks like a change."""
    import subprocess

    from factory.fingerprint import fingerprint

    (tmp_path / "a.py").write_text("x = 1\n")
    before = fingerprint(tmp_path)
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@localhost",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@localhost",
    }
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "b"]):
        subprocess.run(cmd, cwd=tmp_path, env=env, check=True, capture_output=True)
    assert fingerprint(tmp_path) == before, ".git must not affect the fingerprint"


# --- adapter selection -------------------------------------------------------


def test_executing_roles_reject_a_toolless_adapter(monkeypatch):
    """A plain LLM adapter has no shell, so it cannot verify anything.

    GeminiAdapter is an LLM adapter, not a coding agent. Putting the Verifier on it
    would produce an agent that must run pytest and cannot. Fail loudly at startup
    rather than mysteriously mid-run.
    """
    import pytest as _pytest

    from factory import build as build_mod
    from factory.roles import BUILDER, GATEKEEPER, VERIFIER

    for role in (BUILDER, VERIFIER):
        monkeypatch.setenv(f"ADAPTER_{role.key.upper()}", "gemini")
        with _pytest.raises(SystemExit, match="must run commands"):
            build_mod.adapter_kind(role)

    # The Gatekeeper rules on evidence and needs no tools, so it may use one.
    monkeypatch.setenv("ADAPTER_GATEKEEPER", "gemini")
    assert build_mod.adapter_kind(GATEKEEPER) == "gemini"


def test_roles_default_to_the_local_claude_subscription(monkeypatch):
    from factory import build as build_mod
    from factory.roles import ROLES

    for role in ROLES.values():
        monkeypatch.delenv(f"ADAPTER_{role.key.upper()}", raising=False)
        assert build_mod.adapter_kind(role) == "claude"


def test_gemini_without_a_key_fails_with_a_useful_message(monkeypatch):
    import pytest as _pytest

    from factory import build as build_mod
    from factory.roles import GATEKEEPER

    monkeypatch.setenv("ADAPTER_GATEKEEPER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with _pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        build_mod.adapter_for(GATEKEEPER, "prompt")


def test_emit_set_respects_what_each_adapter_supports():
    """Passing an unsupported emit kind is a hard error at construction.

    GeminiAdapter has no thoughts stream, so the Claude emit set crashes it with
    BandConfigError rather than degrading. Keep the per-adapter mapping honest.
    """
    from band import Emit

    from factory.build import EMIT_ALL, EMIT_BY_ADAPTER

    assert Emit.THOUGHTS in EMIT_BY_ADAPTER["claude"]
    assert Emit.THOUGHTS not in EMIT_BY_ADAPTER["gemini"], "Gemini cannot emit thoughts"
    for kind, emits in EMIT_BY_ADAPTER.items():
        assert Emit.TOOL_CALLS in emits, f"{kind} must show tool calls in the room"
        assert set(emits) <= set(EMIT_ALL)


def test_gemini_gatekeeper_builds_when_a_key_is_present(monkeypatch):
    from factory import build as build_mod
    from factory.roles import GATEKEEPER

    monkeypatch.setenv("ADAPTER_GATEKEEPER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    adapter = build_mod.adapter_for(GATEKEEPER, "prompt")
    assert type(adapter).__name__ == "GeminiAdapter"

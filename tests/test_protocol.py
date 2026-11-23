"""Protocol tests. These run with no BAND account, no room, and no model key.

They prove the two properties the factory is judged on:
  * a handoff is *dependent* -- the receiver gets the specific finding, not the task
  * a verdict is *blockable* -- the Gatekeeper's BLOCKED routes back and nothing ships
and the one property that makes it not fall over: context survives every hop.
"""

from __future__ import annotations

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

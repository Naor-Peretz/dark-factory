# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A crew of four BAND SDK agents that take a spec and autonomously plan, write, test, and
decide what ships. Built for The Dark Factory Virtual Buildathon Week ([SF] HackerSquad +
BAND AI), **deadline Sun 29 Nov 2026 17:00 Israel time**. The effective cutoff is Friday
27 Nov sundown — see the Schedule table in `docs/FACTORY_DESIGN.md`.

Read `docs/FACTORY_DESIGN.md` before changing the architecture. It records the design
rationale, the judging criteria the design targets, and verified API shapes.

## Commands

```bash
# setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# tests -- run with no BAND account, no room, no model key
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_protocol.py::test_envelope_round_trips_through_room_text

# validate credentials before a live run (never prints a key)
.venv/bin/python scripts/check_config.py

# run one agent (each role is its own process, one WebSocket per agent)
.venv/bin/python -m agents.run architect   # | builder | verifier | gatekeeper
.venv/bin/python -m agents.run builder -v  # debug logging
.venv/bin/python -m agents.run architect --no-spec
```

There is no linter or formatter configured.

`scripts/register_agents.py` is **Enterprise-gated and refuses to run** — the Human API it
calls returns `403 plan_required` on a free plan. Don't suggest it as the setup path; the
free-plan route is four manual "Connect remote agent" dialogs (`docs/SETUP.md`).

## BAND's three rules — these constrain every design decision

BAND is a *coordination layer* (rooms, `@mention` routing, event log), not an agent
framework. It hosts no models. Violating any of these breaks the factory silently:

1. **A mention carries no context.** An unmentioned agent sees nothing, cannot read room
   history, and can never look the message up later. An agent added mid-run has no
   history at all. This is the number-one cause of a stalled factory.
2. **Every turn must end in a tool call** — `band_send_message`, `band_no_reply`, or an
   action tool. Otherwise BAND marks the message failed and posts an error event. No
   nudge, no retry, work lost.
3. **Plain model text never reaches the room.** Only `band_send_message` does.

Routing is deterministic: the mention decides delivery, no model arbitrates. Agents never
receive their own messages, nor other agents' events.

## Architecture

**`factory/handoff.py` is the load-bearing piece.** Because of rule 1, every handoff must
restate the spec, acceptance criteria, and open findings. The `Handoff` envelope makes
that structural rather than something each prompt must remember — `forward()` carries
context by construction. It renders as human-readable Markdown on purpose: the room
transcript is part of the submission, and a visible `### Prior findings (must be
answered)` block is the evidence that handoffs are *dependent* (a judging criterion).
If you add a station, route through `forward()`; never hand-build a message.

**`factory/roles.py` is the control flow.** Since routing is deterministic, the topology
table *is* the factory's state machine:

```
Architect --@Builder--> Builder --@Verifier--> Verifier --@Gatekeeper--> SHIP
                            ^                      |
                            +--- finding ----------+        (dependent handoff)
Gatekeeper --BLOCKED--> Architect                            (blockable verdict)
```

`Verifier.on_reject == "Builder"` and `Verifier.forward_to == "Gatekeeper"` — a failure
must never reach the ship decision. A test asserts this.

**`factory/build.py`** constructs one adapter per role. Role boundaries are *enforced*
by workspace isolation, not by switching tools off: Builder and Verifier get
`cwd=workspace/repo`, while Architect and Gatekeeper get **no `cwd`**, so the adapter
hands each an empty `.band-workspaces/<room_id>` and the repo is simply not theirs.
**Never set `permission_mode="plan"`** — see "Things that will bite you".

**`prompts/_common.md`** is prepended to every role's mandate and restates the three rules.
If you edit it, you edit all four agents. Role mandates follow the same shape: what it
owns / what it may not do / your turn / done means.

## Things that will bite you

- **The published BAND docs contradict each other** across versions (tutorials pin 6.0.1,
  reference pages say 9.1.0, installed is **9.3.0**). Never copy a doc snippet. Introspect
  the installed package: `.venv/bin/python -c "import inspect; from band.adapters import
  ClaudeSDKAdapter; print(inspect.signature(ClaudeSDKAdapter.__init__))"`.
- **Adapter config fields go in the `*AdapterConfig` object**, never as constructor
  kwargs (raises `TypeError`). Only `emit`, `capabilities`, `include_tools`,
  `exclude_tools`, `include_categories` are constructor kwargs.
- **`agent_config.yaml` must never sit inside a coding agent's `cwd`.** Claude Code could
  read it and a tool result could post the API key into the room. That is the only reason
  `workspace/repo/` exists separately from the project root.
- **All four agents authenticate off the local `claude login` subscription** — no API key,
  no per-token cost. Don't add an `ANTHROPIC_API_KEY` requirement.
- **`VERIFIER_ADAPTER=claude|codex|gemini`** swaps only the Verifier's model family. A
  cross-family critic is a judging criterion; keep that swap a one-variable change.
- **`permission_mode="plan"` silently breaks an agent.** It blocks *every* tool call,
  `band_send_message` included, so the agent produces a perfect handoff and then cannot
  send it — the room logs "Cannot call mcp__band__band_send_message while in plan mode"
  and the turn ends without a reply. Every role must be `acceptEdits`. A test enforces this.
- **`band.testing`** provides `FakeAgentTools`, `FakePhoenixServer`, scripted turns, and
  `assert_message_sent(mentions=…)`. Test protocol changes there — a live room is slow and
  costs tokens. Note `ChatParticipant` and `Peer` are different schemas with different
  required fields; `tests/test_protocol.py` has `_agent()` and `_peer()` helpers.

## Spec handling

The spec is a swappable input file in `spec/` with an `## Acceptance criteria` section
(`factory/spec.py` parses it; `rev: N` at the top sets the revision). `spec/auth-rate-limit.md`
is a **placeholder**, not the real challenge — the real one is behind login on the
HackerSquad dashboard and had not been retrieved as of the last commit. Replacing it is a
drop-in; don't restructure code to accommodate a new spec.

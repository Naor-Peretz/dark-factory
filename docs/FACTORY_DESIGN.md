# Dark Factory — design scope

**Event:** The Dark Factory Virtual Buildathon Week ([SF] HackerSquad + BAND AI)
**Challenge opened:** Sun 22 Nov 2026 · **Deadline:** Sun 29 Nov 2026, 17:00 Israel time
**Brief:** "One challenge. One week. Build a software factory that runs itself."
Build a crew of AI agents that turns a spec into working software on its own — the agents
plan, write, test, and decide what's ready to ship.

---

## 1. What BAND actually is (and isn't)

BAND (band.ai, Thenvoi AI Ltd.) is a **coordination layer**, not an agent framework.
From the docs overview: agents of any framework, on any machine, owned by anyone, work
together in shared rooms by chatting and mentioning each other.

We keep our own agent code, prompts, tools and model keys. BAND supplies:
identity, rooms, `@mention` routing, contacts/permissions, and a replayable event log.
BAND hosts no models — we bring our own keys.

Two products:
- **SDK** (`band-sdk`, Python; `@band-ai/sdk`, TS) — connects *our* agent processes to BAND.
- **BAND Desktop** — a desktop app that runs locally installed coding agents as BAND agents.

### ⚠ The Desktop trap

The Luma blurb says "agents coordinate in BAND Desktop". BAND's own Hacker Guide says the
opposite for a *submission*: using a Desktop build crew is **not your project's use of BAND**.
A judged project's agents should be **SDK agents in rooms**.

**Decision: we build SDK agents.** Desktop is a dev convenience at most, never the deliverable.

---

## 2. Verified environment (ground truth, not docs)

Introspected from the actually-installed package, because the doc pages contradict each other
(tutorials pin 6.0.1, reference pages say 9.1.0, install gives 9.3.0).

| Thing | Value |
|---|---|
| `band-sdk` | **9.3.0** (newer than every doc page) |
| Python | 3.12.3 ✓ (SDK wants >=3.11,<3.14) |
| Node / pnpm | 22.18.0 / 10.28.0 (TS SDK viable but not chosen) |
| Docker | 29.7.2 ✓ (available for sandboxed agents) |
| `uv` | not installed — using `.venv` + `pip` instead, which works fine |

**Verified API shapes (9.3.0):**

```python
Agent.create(adapter, agent_id, api_key, ws_url=None, rest_url=None, config=None,
             session_config=None, contact_config=None, on_participant_added=None,
             on_participant_removed=None, preprocessor=None) -> Agent
Agent.from_config(name, *, adapter, config_path=None, **kwargs) -> Agent
Agent.run(shutdown_timeout=30.0, *, install_signal_handlers=True)
Agent.run_forever(*, install_signal_handlers=True)
```

```python
ClaudeSDKAdapter(config=None, *, history_converter=None, additional_tools=None,
                 workspace_for_room=None, **features)
```

This **resolves the doc's self-contradiction**: config fields go in the `*AdapterConfig`
object (passing them as kwargs raises `TypeError`), while `emit` / `capabilities` /
`include_tools` / `exclude_tools` / `include_categories` are separate `**features` kwargs.

`Emit`: `TOOL_CALLS`, `THOUGHTS`, `TASK_EVENTS`, `USAGE`
`Capability`: `MEMORY` (Enterprise only), `CONTACTS`, **`FILES`**, `TASKS`

> `Capability.FILES` appears in 9.3.0 but in none of the doc pages we read. It is likely the
> chat file upload/download surface — worth using to pass specs and diffs as artifacts
> instead of pasting them into messages. **Needs verification.**

48 adapters are available, incl. `ClaudeSDKAdapter`, `CodexAdapter`, `OpencodeAdapter`,
`LangGraphAdapter`, `CrewAIAdapter`, `PydanticAIAdapter`, `AnthropicAdapter`, `CursorACPAdapter`.

---

## 3. The three rules that constrain every design

These come from BAND's routing semantics and will bite us if ignored.

1. **Context does not travel with a mention.** An unmentioned agent sees *nothing* — the
   message never enters its context and it cannot read it later. An agent added mid-run has
   no history. ⇒ **Every handoff message must carry the spec, constraints, and prior findings.**
   This is the single biggest source of silent failure.
2. **Every turn must end with a tool call** — `band_send_message`, `band_no_reply`, or an
   action tool like `band_add_participant`. Otherwise BAND posts an error event and the
   message is marked failed. **No nudge, no retry.** ⇒ Restate this in every `custom_section`.
3. **Plain model text never reaches the room.** Only `band_send_message` does.

Also: agents never receive their own messages, never receive other agents' *events*,
and routing is deterministic (no model decides who gets what).

---

## 4. How we get judged — BAND's "meaningful use" bar

The Hacker Guide's test: **"Take the room out of your design. Does the app still work?"**
If yes, it reads as a single-agent app with a chat log bolted on.

Judges look for at least one of these. **We are targeting three:**

| Criterion | Our mechanism |
|---|---|
| ✅ A **dependent handoff** — the next agent answers the *finding*, not the task | Verifier reports failing evidence; Builder answers that specific failure, not the original spec |
| ✅ A **roster decided at runtime** | Architect calls `band_lookup_peers` → `band_add_participant` to pull in a specialist only when the spec needs one |
| ✅ A **verdict that can be blocked** | Gatekeeper is mentioned on every ship verdict and can reply `BLOCKED` |
| ⬜ A boundary BAND enforces | (contacts / mention-scoped visibility — not our focus) |

---

## 5. Proposed crew

Four SDK agents, four processes, four registrations (own `agent_id` + `api_key` each).
One room. Only one live WebSocket per agent.

```
                    spec (human, one mention)
                             │
                             ▼
   ┌──────────── ARCHITECT ─────────────┐   plan + acceptance criteria
   │  ClaudeSDKAdapter, no repo write   │   may recruit a specialist at runtime
   └────────────────┬───────────────────┘
                    │ @Builder  (carries spec + criteria)
                    ▼
   ┌──────────── BUILDER ───────────────┐   writes code
   │  ClaudeSDKAdapter, cwd = ./repo    │   permission_mode = acceptEdits
   └────────────────┬───────────────────┘
                    │ @Verifier (carries diff + criteria)
                    ▼
   ┌──────────── VERIFIER ──────────────┐   runs tests, produces EVIDENCE
   │  CodexAdapter (different model!)   │   fails → @Builder with the finding
   └────────────────┬───────────────────┘      (dependent handoff)
                    │ @Gatekeeper (carries evidence)
                    ▼
   ┌──────────── GATEKEEPER ────────────┐   SHIP or BLOCKED
   │  AnthropicAdapter, read-only       │   blocked → @Architect, loop
   └────────────────────────────────────┘
```

**Why a different model per role matters:** the Verifier on Codex/GPT and the Gatekeeper on
Claude means the critic is not the author's own judgment. That is the part a single-agent
app cannot imitate.

### Workspace strategy

- Coding adapters default to **one workspace per room**: `./.band-workspaces/<room_id>`.
- Setting `cwd` shares one checkout across rooms. `cwd` and `workspace_for_room` are
  mutually exclusive.
- **Security:** never let `cwd` contain `agent_config.yaml` — Claude Code can read it and
  tool results can post the API key into the room. Our layout keeps the config at the repo
  root and the agents' working checkout in a separate directory.

---

## 6. Risks and open items

| Risk | Mitigation |
|---|---|
| ~~Free-plan room retention~~ | **Not a risk.** Room created 23 Nov, deadline 29 Nov — well inside ~2 weeks. The real constraint is the Friday sundown cutoff (see Schedule). |
| Turn ends without a tool call → silent failure | Restate rule 2 in every prompt; keep `report_turn_failures_to_room=True` (default) while developing |
| `pydantic-ai` + `crewai` extras conflict on `openai` versions | If we use both, give that agent its own environment |
| Human gates are **prompt-based, not enforced** | Do not claim a security boundary; the Gatekeeper is a convention |
| Approval waits count toward `turn_timeout_s` | Set `approvals.wait_timeout_s` below `turn_timeout_s` |
| Docs version drift | Always introspect the installed 9.3.0, never trust a doc snippet |

**Open — needs a decision or a lookup:**
- [ ] **The actual challenge spec.** Not on Luma. It's on the HackerSquad dashboard
      (needs login): `hackersquad.io/builders/dashboard/events/cmvpfnanv001fn023zhpf6ez7/builder`
- [ ] Real submission format + judging rubric (same place). BAND's guide is *not* the event's rules.
- [x] ~~`Capability.FILES` semantics~~ — **confirmed**: it is artifact passing. `FakeAgentTools` exposes `send_room_file(content, filename, caption, mentions)`, `list_room_files()`, `read_room_file(file_id)`. Use it for specs and diffs instead of pasting into messages.
- [ ] Free-tier caps (reported as 20 remote agents / 250 rooms / 20 participants per room — unverified; we need 4 agents, so ample)
- [ ] BAND account + 4 agent registrations at app.band.ai (the API key shows **once**)

## 7. Reference

- Quickstart: https://docs.band.ai/quickstart
- Hacker Guide: https://www.band.ai/hacker-guide
- Platform tools: https://docs.band.ai/reference/sdk/platform-tools
- Mention routing: https://docs.band.ai/features/routing-mentions
- ClaudeSDKAdapter: https://docs.band.ai/connect/claude-agent-sdk
- Sample 3-agent project: https://docs.band.ai/features/introducing-sample-project
- Closest prior art — Qodo's own dark factory:
  https://www.qodo.ai/blog/from-delegation-to-collaboration-inside-qodos-dark-factory/
- Coding-agents example (planner + reviewer, Docker Compose):
  https://github.com/band-ai/band-sdk-python/tree/main/examples/coding_agents


---

## 8. Build status — 23 Nov

### Schedule (solo, Israel time)

| When | Available | Plan |
|---|---|---|
| Mon 23 Nov | until 18:00 | ✅ core protocol + tests (done) |
| Tue 24 Nov | until 14:30 | BAND account, 4 registrations, first live room |
| Wed–Thu 25–26 | full | real challenge spec, end-to-end cycle, demo target |
| Fri 27 Nov | until sundown | **hard cutoff — must be demo-ready.** Record walkthrough. |
| Sat 28 Nov | Shabbat | — |
| Sat night–Sun 29 | until 17:00 | buffer + submission write-up only, not build time |

**The Friday cutoff is the real deadline.** Saturday night plus Sunday morning is buffer,
not capacity. Anything not working by Friday sundown is at risk.

### Done

- Repo, venv, `band-sdk` 9.3.0, 12 passing protocol tests
- `factory/handoff.py` — the handoff envelope. Makes "a mention carries no context"
  structural instead of something the prompt has to remember. Renders as readable
  Markdown because judges read the room; a visible "Prior findings (must be answered)"
  block *is* the evidence of a dependent handoff.
- `factory/roles.py` — four roles + the routing topology, which is the factory's control flow
- `factory/spec.py` — spec is a swappable input file; real challenge is a drop-in
- `prompts/` — `_common.md` (the three hard rules, restated for every agent) + four mandates
- `factory/build.py` — adapter per role; Verifier's is swappable via `VERIFIER_ADAPTER`
- `scripts/register_agents.py` — registers all four and writes `agent_config.yaml` in one shot
- `spec/auth-rate-limit.md` — placeholder target with sharp test signal

### Two decisions made while building

**All four agents run on the local Claude Code subscription.** `claude` 2.1.330 is installed
with subscription credentials and there is no `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in the
environment. `ClaudeSDKAdapter` authenticates off `claude login`, so the whole factory runs
at zero marginal cost. The cross-family critic is deferred, not abandoned — it is one env
var (`VERIFIER_ADAPTER=gemini|codex`) and nothing else changes.

**`permission_mode` enforces the role boundaries.** Architect and Gatekeeper get
`permission_mode="plan"`, so they *cannot* edit files — it is not merely prompt discipline.
Builder and Verifier get `acceptEdits` and a `cwd` of `workspace/repo`, deliberately
separate from the project root so `agent_config.yaml` is never inside a coding agent's
working directory (it would be readable, and a tool result could post the API key to the room).

### The big unblock

`band.testing` ships a full fake: `FakeAgentTools`, `FakePhoenixServer`, `ScriptedTurn` /
`TextTurn` / `ToolTurn` / `ErrorTurn`, `assert_message_sent(mentions=…, count=…)`,
`until_said()`, `MISSING_REPLY_FAILURE`. **The entire protocol is testable with no BAND
account, no room, and no model key.** That is why the crew could be built before the
account exists, and it means a broken handoff is caught in 0.2s instead of in a live room.

### Next

1. BAND account + `scripts/register_agents.py` (needs one `band_u_…` user key)
2. The real challenge spec — blocked on dashboard access (extension not connected)
3. Live room, four processes, first end-to-end cycle on the placeholder spec
4. Then swap the placeholder for the real challenge

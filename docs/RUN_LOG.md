# Live run log

What actually happened when the factory ran, including the parts that went wrong.
This is the honest record; `FACTORY_DESIGN.md` is the design.

---

## Run 1 — 23 Nov 14:28 · the mute planner

All four agents connected and joined the room. The Architect was mentioned, and composed
a correct handoff on its first attempt: seven acceptance criteria derived from the spec,
constraints restated, design guidance, explicit "Prior findings: none (first pass)".

Then it could not send it.

```
"output": "Cannot call mcp__band__band_send_message while in plan mode."
error / Architect: The agent ended its turn without replying or calling
band_no_reply, so nothing reached the room.
```

`permission_mode="plan"` blocks **every** tool call, not just file edits — the Band MCP
tools included. The two roles I had "protected" from editing code were the two that
could not speak. A planning agent in plan mode is mute.

**Fix:** every role runs `acceptEdits`; the boundary becomes workspace isolation
instead. Builder and Verifier get `cwd=workspace/repo`; Architect and Gatekeeper get no
`cwd`, so each receives its own empty workspace and the repo is simply not theirs.

Cost: $0.096.

---

## Run 2 — 14:31 · the Verifier refuses to lie

Chain ran: **Architect → Builder → Verifier → Architect → human**.

The Builder produced a genuinely good limiter — per-IP sliding window over a `deque`,
a `threading.Lock`, an **injectable clock** so the reset test needs no real sleep,
scoped to `/login` only, `Retry-After` clamped to `[1, window]`. Independently confirmed
afterwards: it passes 7/7 oracle tests and 11/11 repo tests.

But the Verifier could not run anything. `acceptEdits` auto-approves file writes, not
shell commands, so every `pytest` came back "This command requires approval" — and an
unattended agent has nobody to approve it. The Verifier's response is the single best
thing that happened all day:

> No criterion has a recorded pass. I am not marking any of them as passing… Handing
> this to the Gatekeeper would be wrong because there is no evidence.

It had the Builder's confident report and a plausible-looking diff. The easy path was to
glance at the code and pass it along. It refused, wrote the blocker as a numbered
finding, and escalated. The Architect then declined to invent a plan change:

> This is an environment defect, not a code defect… I'm not incrementing the rev,
> because the plan was not wrong.

**This is the whole design working.** The factory stalled honestly rather than shipping a
fiction. A stall you can diagnose beats a green you cannot trust.

**Fix:** `ClaudeApprovalOptions(mode="auto_accept")` for the two executing roles only.

---

## Run 3 — 14:34 · BLOCKED on a passing build, and the critic finds a hole in the oracle

With execution unblocked, the Verifier ran both suites and routed to the Gatekeeper.
Ground truth was **7/7 oracle, 11/11 repo**. The Gatekeeper ruled **BLOCKED** anyway,
with three findings — and all three are legitimate:

1. **Criterion 6 unproven.** It says "from a clean checkout"; the Verifier ran in the
   working tree. Also, 6 of those 11 passing tests are *new Builder tests*, so "11
   passed" does not show the pre-existing suite still passes.
2. **"Do not modify the auth handler" has no evidence.** No diff against a baseline was
   ever produced. "Unchanged in appearance" is not output.
3. **The 60s default is unverified.** Every acceptance test builds the app with
   `window_seconds=1`. Nothing exercised `create_app()`'s real defaults, and criteria 1
   and 2 are stated for the default configuration.

**Finding 3 was a real gap in the acceptance oracle I wrote.** The independent critic
found a hole in the independent checker. Three tests were added to close it:
`test_default_configuration_is_ten_requests_per_sixty_seconds`,
`test_eleventh_request_is_throttled_under_the_real_defaults`,
`test_retry_after_is_plausible_under_the_real_defaults`. The oracle is now 10 tests.

This is the "absence of evidence is not evidence" stance earning its place. A Gatekeeper
that ships whatever is green would have shipped here, and three of the seven criteria
would have been unproven.

---

## Run 3b — the approval-notification loop

The run then degenerated. `auto_accept` silently keeps `text_notifications=True`, so
every auto-approved command was **also posted into the room** as
`Approval requested (Bash: ...)`, addressed to the Architect. The Architect answered,
correctly, "I can't approve that — that decision is Naor's." Which re-triggered the
Builder. Seven consecutive `band_no_reply` turns, no progress, real money.

**Fix:** `text_notifications=False`. An approval that is auto-accepted has no audience.

(Note: the SDK field is `text_notifications`; the docs call it
`approval_text_notifications`, which is a different adapter's field and fails validation.)

Cost of the whole session: roughly **$0.84** across all three runs.

---

## What this says about the design

The envelope, the routing topology and the independent oracle all worked on first
contact. Every failure was in the **harness**, not the protocol: a permission mode that
muted an agent, a sandbox that blocked execution, a notification that created a loop.
None of them could have been fixed by better prompts — and two of them were only
visible because an agent reported them honestly instead of papering over them.

Four regression tests now cover them: no role in plan mode, executing roles can run
commands, non-coding roles get no repo access, and auto-accepted approvals stay silent.

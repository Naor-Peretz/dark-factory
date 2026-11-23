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

---

## Run 4 — 14:39 · SHIP on a feature that did not exist

The worst outcome of the day, and the most useful.

I reseeded the workspace to pristine and restarted the agents for a clean run. A Builder
handoff from the previous run was still in flight; on restart the Gatekeeper hydrated it
from room history and ruled:

```
SHIP — spec auth-rate-limit, rev 2
```

Ground truth at that moment: **no limiter in the tree at all**, and the acceptance
oracle failing **5 of 10**. The factory shipped a feature that was not there.

**The Gatekeeper did nothing wrong by its own rules.** The evidence it read was real,
detailed, and described passing tests. It simply described a tree that no longer
existed. Nothing in the protocol tied a test result to the state of the code it was
measured against — so a report could outlive its subject and still be ratified.

This is a deeper failure than the earlier three. Those were harness bugs. This is a
protocol hole: **evidence with no binding to the world is a story about the past.**

### Fix: fingerprint the tree

`factory/fingerprint.py` hashes every source file under the workspace (caches, VCS
metadata and logs excluded) into a short deterministic digest. `scripts/fingerprint.py`
prints it.

- The **Verifier** runs it immediately before its first check and again after its last,
  and puts both readings at the top of its Evidence. Matching hashes mean the tree held
  still; differing hashes void the run.
- The **Gatekeeper** blocks before reading a single result if the evidence carries no
  fingerprint, carries only one reading, or carries two that disagree.

Four tests cover it: determinism, content-sensitivity, cache-insensitivity, and that
both prompts actually carry the rule.

### The gap that remains

The Verifier's two readings catch a tree that moves *during* verification. They do not
catch a tree that moves *between* the Verifier finishing and the Gatekeeper ruling —
which is exactly what happened in this run.

Closing that needs the Gatekeeper to recompute the hash itself at verdict time, which
means giving it read access to the workspace. That trades away part of the boundary
that currently makes it a clean judge: it has no `cwd` and cannot reach the code at all.
**Deliberately left open pending a decision** — the honest state is that the factory can
now detect a tree that shifts mid-verification, and cannot yet detect one that shifts
mid-verdict.

---

## Run 5 — 14:56 · all four fixes hold, and the Gatekeeper finds a defect in the setup

First run in a **fresh room** (no stale history) against a pristine workspace. Clean
chain: **Architect → Builder → Verifier → Gatekeeper**. No mute planner, no approval
refusals, no notification loop. All four earlier fixes confirmed under live conditions.

**The fingerprint worked.** The Verifier stamped both readings and the Gatekeeper
checked them before reading a single result:

> Fingerprint check passed: the two WORKSPACE-FINGERPRINT readings are both
> b2f4e5dd8071203a, so the tree held still. The block rests on the findings below, not
> on the fingerprint.

Ground truth this time: the Builder's limiter passed **10/10 acceptance and 9/9 repo
tests**. Genuinely complete work.

It was still **BLOCKED**, on three findings, and all three were right:

1. **Criterion 6 is unmeasurable as set up.** It says "from a clean checkout", but
   `workspace/repo` had no git history, so no checkout could be clean. The Verifier ran
   in the working tree, which also contains the Builder's *new* tests — so "9 passed"
   never showed the *original* suite still passing.
2. **No raw output was pasted.** The Verifier gave counts, test names and exit codes. A
   summary is a claim; block-by-default means claims do not count.
3. **Vacuity was not demonstrated.** No evidence that the passing tests could have failed.

Finding 1 is a defect in **my** scaffolding, not the agents'. The criterion was written
to be checkable and then placed in an environment where it could not be checked.

### Fixes

- `scripts/seed_workspace.py` now gives the checkout its own git repo with a pristine
  baseline commit. `git stash -u && pytest && git stash pop` proves the original suite;
  `git diff HEAD -- app.py` proves the handler is untouched. Both were previously
  unprovable, and the Gatekeeper had flagged the diff gap back in run 3 as well.
- The Verifier's prompt now carries both recipes, requires the **raw transcript** rather
  than a summary, and requires saying why each test could have failed.
- The fingerprint ignores `.git`, so a baseline commit does not look like a change. Tested.

### The pattern across five runs

The Gatekeeper has now blocked two builds that passed every test, and been right both
times — once finding a hole in the acceptance oracle, once finding that a criterion was
unmeasurable. Neither was a code defect. Both were defects in how the work was being
*proved*, which is exactly what a gate is for and exactly what a crew of agents
agreeing with each other would have waved through.

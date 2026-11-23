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

---

## Run 6 — 15:36 · two rooms, one checkout

First run with the Gemini Gatekeeper. It connected and the cross-family crew was real:
three Claude agents and one Gemini judge, all local processes.

The run was ruined by something I had read about and then walked into anyway.

An agent joins **every** room it is a participant of. Both older rooms still had
unprocessed messages, so on restart the agents resumed those cycles *as well as* the
new one. And because the coding roles were configured with an explicit `cwd`, every
room shared **one checkout**. Two Builders were editing the same files at the same
time. The fingerprint shifted from `341c4568…` to `e1578809…` mid-run.

The Band docs say it plainly: two rooms sharing `cwd` edit the same checkout. I set
`cwd` for the convenience of a fixed path and lost room isolation in exchange.

### Fix: one checkout per room

`workspace_for_room=create_room_workspace_resolver(workspace/rooms)` replaces `cwd`,
so every room gets `workspace/rooms/<room_id>`. The two are mutually exclusive, which
is the SDK telling you to choose isolation or convenience.

- `scripts/seed_workspace.py <room_id>` seeds one room and gives it a baseline commit.
- `scripts/fingerprint.py <room_id>` hashes that room's checkout.
- The Verifier derives its room from its own working directory:
  `python scripts/fingerprint.py "$(basename "$PWD")"`.

Architect and Gatekeeper still get no checkout at all.

A stale room can now churn harmlessly in its own directory. It still costs tokens, so
the operational lesson stands: **remove the agents from rooms you are finished with**,
or they will resume mid-conversation whenever the processes restart.

### What this run did confirm

- The Gemini Gatekeeper starts, holds its WebSocket and joins rooms. No auth or quota
  errors from the free tier.
- The crew is genuinely cross-family now: the judge is not the author's model.
- The fingerprint caught the corruption. It shifted exactly when two Builders touched
  one tree, which is precisely the case it was built for — detected on the very next
  run after it was added.

---

## Run 7 — 15:53 · a clean, legitimate SHIP

The run the factory was built for. Chain:
**Architect → Builder → Verifier → Gatekeeper → SHIP**, no human in the inner loop.

Ground truth, checked independently afterwards: **10/10 acceptance, 12/12 repo tests**.
This time the verdict was correct *and* well-evidenced.

### What the Gatekeeper actually did

- **Bound the verdict to a tree.** `WORKSPACE-FINGERPRINT: ec312b2feaa81d89` before and
  after, clean `git status`. It said so explicitly before reading any result.
- **Refused to re-ratify stale work.** The room still held a SHIP from an aborted
  earlier cycle. It wrote: "This is fresh evidence, not a re-ratification of the
  earlier 516251b cycle."
- **Weighed evidence rather than counting it.** The line that matters most:

  > the acceptance suite had 5 of 10 tests fail on baseline, which gives the real
  > signal. The Builder's 7 new tests fail there only because of the missing `clock=`
  > kwarg, so they are weak evidence.

  It separated tests that fail on baseline *for the right reason* from tests that fail
  for an incidental one, and discounted the author's own tests accordingly. That is the
  vacuity check working at a level the prompt only gestured at.
- **Checked the constraint literally.** The `login` handler body is byte-identical; the
  only removed line is the `create_app` signature becoming multi-line.
- **Listed "caveats that didn't block".** Proportionate judgment, not blocking on
  everything it could not see.

The Verifier also ran a concurrency probe nobody asked for: 200 requests across 10
threads with a budget of 50, giving exactly 50 non-429 and 150 429.

And the Architect, closing the loop to the human, wrote: "I haven't checked this myself.
The results below are the Verifier's and Gatekeeper's." Correct attribution of what it
knew versus what it was told.

### Two fixes this run produced

- **Stale processes hold Band's single-instance lock.** The Architect and Gatekeeper
  died at startup with `AgentAlreadyRunningError` because a prior launch had survived
  and the pid files only knew the last one. `stop_factory.sh` now sweeps by process
  pattern and clears `/tmp/band-agent-*.lock`.
- **`fingerprint.py` required a room id**, so the Verifier's first call printed usage
  and wasted a turn. It now infers the room from the working directory, which is where
  the Verifier already stands.

### Gemini was down

The Gatekeeper ran on Claude for this one. Gemini returned 503/504 across 3.8-flash,
3.5-flash and 3.7-flash ("this model is currently experiencing high demand") — Google
capacity, not configuration. The key authenticates and the adapter connects, verified
earlier. `.env` carries `ADAPTER_GATEKEEPER=claude` with the gemini line commented
directly above it; flip it back when the API recovers.

### Recording

`runs/factory.gif` — six frames of the room filling up, kickoff to verdict, built with
Pillow (no ffmpeg needed) via `scripts/make_gif.py`.

---

## Run 8 — 16:13 · the memory loop closes

cognee wired in as the factory's memory across cycles. First attempt, the Architect
explored the tooling, probed for the virtualenv, gave up and planned without consulting
memory at all. Two fixes: the prompt now names the interpreter outright
(`/…/.venv/bin/python /…/scripts/memory.py`) instead of a bare `python`, and recall is
step one of the turn rather than a section further down.

Second attempt it worked, and the result is better than the instruction asked for.

**The Architect turned remembered lessons into new acceptance criteria.** The spec went
from 7 criteria to 10, and each addition traces to something the factory learned earlier
the same day:

| New criterion | The lesson behind it |
|---|---|
| 9. `create_app()` with **no arguments** throttles the 11th request | "an acceptance suite that only exercises a short test window never checks the production defaults" |
| 10. new tests "must fail on the baseline **for behavioural reasons**, not only because of an unknown kwarg" | "tests that pass on the baseline prove nothing; a test failing only on a changed signature is weak evidence" |
| 6. now proved in "a fresh `git worktree` at the baseline commit" | "a clean-checkout criterion is unprovable unless the workspace has a baseline commit" |

Criterion 10 is the striking one. The Gatekeeper worked out the strong-versus-weak
evidence distinction on its own in run 7, that reasoning was stored as a lesson, and in
run 8 the Architect promoted it to a requirement the Builder must satisfy up front. The
crew's judgment became part of the spec.

It also cited each lesson inline as `[MEMORY/architect]` beside the criterion it
produced, rather than using the separate `### Prior lessons` section the prompt asked
for. That is the better shape — it shows why a requirement exists instead of leaving a
reader to guess — so the prompt was changed to match the agent rather than the reverse.

### Why cognee here is not a sponsor sticker

Band's `Capability.MEMORY` is Enterprise-only, so without this the crew genuinely starts
every run cold. The gap is real, and what fills it is doing real work: the factory now
arrives at a cycle already knowing what tripped it last time.


---

## Runs 9 and 10 — the factory repairs its own evidence

Left running, the crew completed two more cycles unattended. The lessons it wrote are
the point, so they are quoted in full.

**After cycle 3** it recorded what worked *and* named its own weak spots:

> Criteria that worked: a no-argument `create_app()` criterion (real defaults) plus a
> criterion that new tests must fail on baseline for behavioural reasons, with failure
> text quoted by the Verifier. Result: 4 of 6 new-test baseline failures were
> behavioural (assert 200 == 429, missing Retry-After header) and only 2 were
> clock-signature errors. **Weak spots left open: nobody confirmed which app.py the
> baseline acceptance run imported, and criterion 7 passes on baseline so it is only a
> regression guard.**

**After cycle 4** it had closed both:

> Adding a baseline-provenance criterion (Verifier prints `app.__file__` for the
> baseline run, proving it imported the baseline worktree) closed the cycle-3 gap, and
> pairing the valid-credentials check with an 11th-request-429 assertion in one test
> made criterion 7 fail on baseline (assert 200 == 429), so it is no longer vacuous.
> 5 of 7 new-test baseline failures were behavioural. Still open: time is faked in
> every test so wall-clock behaviour is untested; the Verifier did not re-paste the
> app.py diff.

The factory diagnosed a weakness in how it proves things, wrote it down, and repaired it
on the next pass without being asked — then left itself a fresh note about the next
weakness (faked clocks) for the cycle after.

**Verified, not taken on trust.** The lesson names commit `2856b1d` on baseline
`d037eed`; `git log` in the room checkout shows exactly those SHAs. Ground truth at the
end: 10/10 acceptance, 13/13 repo tests — one more repo test than cycle 3, which is the
test it added to close its own gap.

### Session cost

Roughly **$1.46** across all four agents for ten cycles, on top of the earlier runs.

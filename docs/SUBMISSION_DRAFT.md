# Submission draft

Paste-ready content for the HackerSquad project form. Update the numbers from the final
run before submitting — do not ship stale figures.

---

## PROJECT.NAME

```
Dark Factory
```

## PROJECT.STACK

- [x] **Band** — the coordination layer the whole factory runs on
- [ ] **cognee** — tick only if the memory layer actually ships
- Other stack: `Python 3.12, band-sdk 9.3.0, Claude Agent SDK, Flask, pytest`

## GIT.REMOTE

```
https://github.com/Naor-Peretz/dark-factory
```

## PRE-EXISTING CODE

```
Nothing pre-existed. The repository was created on 23 Nov 2026, during the event, and
every commit is from the build week. It was started before the challenge page was read,
since the organisers had not published a challenge statement, rules or rubric — the Luma
description was the entire brief.

The demo target (a small Flask auth service with no rate limiting) and the acceptance
suite are mine, written as inputs for the factory to consume. The factory's output is
the rate limiter in workspace/repo, which its own agents wrote, tested and ruled on.
```

---

## PROJECT.README

```
One challenge. One week. Build a software factory that runs itself.

Dark Factory is a crew of four Band SDK agents that take a spec and carry it to a ship
decision with no human in the inner loop. Architect plans, Builder writes, Verifier
produces evidence, Gatekeeper rules SHIP or BLOCKED. Each is its own process with its
own Band identity, and they coordinate only by @mention in one room.

WHAT MAKES IT A FACTORY RATHER THAN A CHAT LOG

Take the room out of the design and it stops working. Three mechanisms depend on it:

1. Dependent handoffs. The Verifier does not return "the task failed" — it returns a
   numbered finding, and the Builder's next message must answer that specific defect.
   Because a Band mention carries no context whatsoever (an unmentioned agent sees
   nothing and can never read the message later), every handoff is a structured
   envelope that re-states the spec, the criteria and every open finding. That is
   factory/handoff.py, and it is the load-bearing piece.

2. A verdict that can be blocked. The Gatekeeper is mentioned on every ship decision and
   blocks by default: absence of evidence is not evidence. It has no repo access and
   rules only on what the Verifier can show.

3. A roster decided at runtime. The Architect can band_lookup_peers and
   band_add_participant to recruit a specialist mid-run — and because a newly added
   agent has no history, its first mention must carry the whole spec.

AN INDEPENDENT ORACLE

The Verifier owns an acceptance suite the Builder cannot read or edit. The Builder's cwd
is the checkout; the Verifier gets that plus the oracle directory via add_dirs. A critic
that reads the author's own tests is not a check, and one that can edit them is no check
at all. The oracle deliberately probes what a Builder writing its own tests would miss —
a shared global bucket that throttles the 11th request while violating the per-IP
constraint, and a Retry-After that exists but is not a plausible number.

EVIDENCE IS BOUND TO A TREE

Test results are a claim about one specific state of the code. The Verifier stamps its
evidence with a workspace fingerprint before its first check and after its last; the
Gatekeeper blocks evidence that is unstamped or whose readings disagree. This exists
because the factory once shipped a rate limiter that was not in the tree: the verdict
was made against a report that had outlived its subject.

WHAT WE LEARNED BY RUNNING IT

Four live runs, all documented honestly in docs/RUN_LOG.md including the failures:

- permission_mode="plan" mutes an agent. It blocks every tool call, band_send_message
  included, so the Architect composed a perfect handoff and could not send it.
- acceptEdits does not cover shell commands, so the Verifier could not run pytest. It
  responded by refusing to pass work it had not tested — "handing this to the Gatekeeper
  would be wrong because there is no evidence" — which is the system working.
- auto_accept still announces each approval in the room, which another agent answers,
  which loops.
- The Gatekeeper blocked a build passing 7/7 acceptance and 11/11 repo tests, and was
  right: the 60s defaults were never exercised, "clean checkout" was never demonstrated,
  and no baseline diff proved the auth handler untouched. It found a genuine hole in the
  acceptance oracle itself.

Every failure was in the harness, not the protocol, and none could have been fixed by
better prompts. 23 tests cover the protocol and run with no Band account and no model
key, using band.testing's FakeAgentTools.
```

---

## Demo video — shot list

Keep it tight. Show the room, not the code.

1. **The room, four agents.** Participants panel: Architect, Builder, Verifier, Gatekeeper.
2. **One human message.** `@Architect` plus the spec. Then hands off the keyboard.
3. **The handoff envelope.** Scroll the Architect → Builder message: criteria carried
   verbatim, constraints, "Prior findings: none".
4. **The dependent handoff.** A Verifier finding, then the Builder answering that
   specific defect — not the original task.
5. **The block.** The Gatekeeper's BLOCKED with numbered findings on a build whose tests
   pass. This is the money shot: say out loud that the suite was green and it still
   refused.
6. **The fingerprint.** Two matching hashes in the evidence; state what a mismatch does.
7. **Close on the test that matters:** take the room out and none of this works.

Mention the failures briefly. A team that says "our Gatekeeper once shipped something
that did not exist, here is the fix" is more credible than one claiming a clean run.

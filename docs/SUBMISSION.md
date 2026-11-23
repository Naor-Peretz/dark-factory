# Submission requirements

Read from the HackerSquad builder dashboard on 23 Nov 2026. Event slug:
`band-dark-factory-buildathon-san-francisco-2`, event id `cmvpfnanv001fn023zhpf6ez7`.

## The headline: the organizers have published almost nothing

| What | Dashboard says |
|---|---|
| Challenge statement | **absent** — nothing beyond the Luma description |
| Rules / eligibility | "Check with the event team before making assumptions" |
| Judging rubric | "A detailed rubric isn't published for this judging stage" |
| Submission deadline | **"Not announced yet — check with the event team"** |
| Prizes | "Prizes haven't been announced yet" |
| Demo length / extra deliverables | "The organizers haven't added extra submission or demo instructions yet" |

So the Luma copy (build a crew of agents that turns a spec into working software; submit
by Sun 29 Nov 17:00 Israel time) remains the **only** statement of the task, and the
29 Nov deadline is unconfirmed by the official dashboard.

**Ask the event team on Discord:** https://discord.com/invite/5YkNXmYfjk
Specifically: the real deadline, whether a rubric exists, and demo video length.

With no published rubric, BAND's own "meaningful use" criteria (see `FACTORY_DESIGN.md`
§4) stay the best available proxy — they are the sponsor's stated expectations.

## The submission form — concrete and binding

Three gated steps: **save project → record video demo → submit**.
`SUBMIT FOR JUDGING` is **disabled** until a video exists. Form text: "click Save project
first, then record a video demo to unlock Submit."

> save as often as you like throughout the day — judges only see your project once you submit.
> After submitting, you can keep saving updates; judges see your latest saved version.

Fields:

| Field | Note |
|---|---|
| `PROJECT.NAME` | |
| `PROJECT.README` | free text description |
| `PROJECT.STACK` | checkboxes: **Band**, **cognee**, plus free-text "other stack" |
| `TEAM.ROSTER` | pulled from the Team tab; solo = empty |
| `GIT.REMOTE` | **a GitHub URL is required.** "Save your project to check this repository. The check runs in the background and does not block submission." → **https://github.com/Naor-Peretz/dark-factory** (public, pushed 23 Nov) |
| `PRE-EXISTING CODE` | optional: "did you start with an existing project, fork, or template? Tell judges what already existed and what your team built during this hackathon." |
| consent checkbox | judging partners may contact by email |

## Three things this forces

1. ~~**A public GitHub repo.**~~ ✅ **https://github.com/Naor-Peretz/dark-factory** —
   created and pushed 23 Nov. Commits use the GitHub `noreply` address rather than the
   account's private email, because GitHub's email-privacy protection (GH007) rejects
   pushes that would expose it; the alternative was making the address public, which is
   worse. Verified before publishing: no secrets tracked, `agent_config.yaml` / `.env` /
   `.agent_ids.txt` all ignored.
2. **A video demo. Mandatory — it blocks submission.** Not a nice-to-have. This is the
   artifact that has to show the room: four agents, the dependent handoff, a blocked
   verdict. Budget real time for it before Friday sundown.
3. **An honest pre-existing-code note.** This repo started 23 Nov, during the event, but
   it did start before the challenge statement was read. Say exactly that; the field
   explicitly asks what existed versus what was built.

## cognee — the second sponsor

The dashboard says **"2 tools in play. Ship with them, get scored."**

- **Band** — Foundation Sponsor, 1 tool
- **cognee** — Silver Sponsor, 1 tool: "Memory in 5 lines of code! Unlock cognitive
  abilities for AI apps and agents." https://www.cognee.ai/

`PROJECT.STACK` has a checkbox for each, so stack choice is recorded and, per the
dashboard's own wording, scored.

**This is not decoration — it fits a real hole in the factory.** BAND's `Capability.MEMORY`
is Enterprise-only, so our agents have no memory across cycles: every run starts cold and
a finding from yesterday's run is gone. cognee as the factory's memory layer would let the
Verifier recall that a previous Builder tried a shared global bucket, or that a criterion
was mis-specified before. That is a genuine capability gain, not a sponsor sticker.

**Decision needed** — it is scope, and the Friday cutoff is real. See `FACTORY_DESIGN.md`.

## Status / points

`0 PTS` · `Demo: Not requested` · `Project: Missing` · 36 hackers connected ·
1 project already submitted (appears to be a placeholder: "A project description of
reasonable length"). Giving sponsor-tool feedback earns points
(`$ ./give_developer_feedback.sh → earns points`).

The 22 Nov 17:00–20:00 kickoff at Icon Tower, Menachem Begin 13, Ramat Gan is marked
**Completed** — that was the meetup, not the build week.

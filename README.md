# Dark Factory

A software factory that runs itself: a crew of BAND SDK agents that take a spec and
plan, build, test, and decide what ships — with no human in the loop of the inner cycle.

Built for **The Dark Factory Virtual Buildathon Week** ([SF] HackerSquad + BAND AI).
Deadline: **Sun 29 Nov 2026, 17:00 Israel time**.

## Design

See **[docs/FACTORY_DESIGN.md](docs/FACTORY_DESIGN.md)** — architecture, the three routing
rules that constrain everything, how the build is judged, and open questions.

The crew: **Architect** → **Builder** → **Verifier** → **Gatekeeper**, four separate
processes in one BAND room, coordinating by `@mention`. Verifier runs a different model
family from Builder so the critic is not the author's own judgment.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp agent_config.yaml.example agent_config.yaml   # fill from app.band.ai
cp .env.example .env                             # model provider keys
```

Then register four agents at app.band.ai (Agents → Connect remote agent; the API key is
shown only once), create a room, and add all four.

## Layout

```
agents/    one process per agent
prompts/   custom_section prompt per role, loaded from disk
spec/      the input spec(s) the factory consumes
factory/   shared helpers and custom tools
docs/      design and notes
runs/      run artifacts (gitignored)
```

## Stack

`band-sdk` 9.3.0 (Python 3.12). BAND is the coordination layer only — it hosts no models,
so model keys are ours. API shapes in the design doc were introspected from the installed
package, not copied from docs: the published pages contradict each other across versions.

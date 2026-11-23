# Setup — BAND account and the four agents

## Why this is manual

Programmatic registration (`scripts/register_agents.py`, the Human API
`POST /api/v1/me/agents/register`) **requires an Enterprise plan**. On a free plan it
returns `403 plan_required`, so the script refuses to run. The four-dialog route below
is the only documented free-plan path.

## 1. Account

Sign up at **app.band.ai** — free, no card.

## 2. Register four agents

**Agents → Connect remote agent**, once per role. The description must be at least 10
characters. Use these:

| Name | Description |
|---|---|
| `Architect` | Turns a spec into an executable plan with objectively checkable acceptance criteria. |
| `Builder` | Implements the plan in the repository. Answers verifier findings specifically. |
| `Verifier` | Runs checks against each acceptance criterion and produces real evidence or findings. |
| `Gatekeeper` | Rules SHIP or BLOCKED on the verifier's evidence. Blocks when evidence is absent. |

The **name must match exactly** — mentions resolve by handle, then display name, then ID,
and `factory/roles.py` mentions these names.

⚠ Each agent's `api_key` is shown **once**, in the "Agent Created Successfully!" dialog.
Copy it immediately. If you lose one: Agents → that agent → Agent actions →
Regenerate API key (the new key is also shown once).

## 3. Fill the config

```bash
cp agent_config.yaml.example agent_config.yaml
```

Paste each `agent_id` and `api_key` under the matching role key. The file is gitignored.

**Do not paste keys into a chat.** Fill the file directly.

## 4. Validate

```bash
.venv/bin/python scripts/check_config.py
```

This checks the structure and then calls `GET /api/v1/agent/me` with each credential, so
you learn now rather than mid-demo whether a key is wrong. It never prints a key.

## 5. Create the room

In the web app: create a room, name it after the spec, and **add all four agents**. A
mention only resolves against current participants, and an agent added later has no
history of what came before.

Then start the four processes, each in its own terminal:

```bash
.venv/bin/python -m agents.run architect
.venv/bin/python -m agents.run builder
.venv/bin/python -m agents.run verifier
.venv/bin/python -m agents.run gatekeeper
```

Only **one live WebSocket per agent** is allowed — don't start a role twice.

## 6. Kick it off

Send the first message in the room mentioning `@Architect`. The UI rejects a message with
no mention.

## Security notes

- `agent_config.yaml` must never sit inside a coding agent's `cwd`. Builder and Verifier
  work in `workspace/repo/` precisely so it doesn't — otherwise Claude Code can read the
  file and a tool result could post your API key into the room.
- Key prefixes: `band_a_` = agent key (what you want here), `band_u_` = user key (Enterprise).

"""Run one factory agent.

    python -m agents.run architect

Each role is its own process with its own BAND registration -- only one live
WebSocket per agent is permitted.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from band import Agent, configure_logging  # noqa: E402
from factory import build, prompts, spec as spec_mod  # noqa: E402
from factory.roles import ROLES  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=sorted(ROLES))
    ap.add_argument("--spec", default=None, help="spec id; omit to auto-detect in spec/")
    ap.add_argument("--no-spec", action="store_true", help="start without a spec preloaded")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    role = ROLES[args.role]

    spec_text = None
    if not args.no_spec:
        try:
            spec_text = spec_mod.load(args.spec).text
        except (FileNotFoundError, ValueError) as e:
            print(f"[{role.name}] no spec preloaded: {e}", file=sys.stderr)

    prompt = prompts.build(role, spec_text=spec_text)
    adapter = build.adapter_for(role, prompt)

    print(f"[{role.name}] starting · forwards to {role.forward_to} · prompt {len(prompt)} chars")
    agent = Agent.from_config(role.key, adapter=adapter)
    await agent.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

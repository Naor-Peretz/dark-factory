"""Validate agent_config.yaml and verify each credential against BAND.

Never prints a key. Reports only role, agent id, and whether the credential works.

    .venv/bin/python scripts/check_config.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import yaml  # noqa: E402

from factory.roles import ROLES  # noqa: E402

CONFIG = Path(__file__).resolve().parent.parent / "agent_config.yaml"
REST = "https://app.band.ai"

OK, BAD, WARN = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m!\033[0m"


async def probe(client: httpx.AsyncClient, api_key: str) -> tuple[bool, str]:
    """GET /api/v1/agent/me with this agent's key."""
    try:
        r = await client.get(
            f"{REST}/api/v1/agent/me", headers={"X-API-Key": api_key}, timeout=15.0
        )
    except httpx.HTTPError as e:
        return False, f"network error: {type(e).__name__}"
    if r.status_code == 200:
        body = r.json()
        d = body.get("data", body)
        return True, f"authenticated as {d.get('name') or d.get('handle') or '?'}"
    if r.status_code in (401, 403):
        return False, f"rejected ({r.status_code}) -- key wrong, revoked, or regenerated"
    return False, f"unexpected {r.status_code}"


async def main() -> int:
    if not CONFIG.exists():
        print(f"{BAD} {CONFIG} not found.")
        print("\n  cp agent_config.yaml.example agent_config.yaml")
        print("  then fill it from app.band.ai -> Agents -> Connect remote agent (x4)")
        return 2
    if CONFIG.is_dir():
        print(f"{BAD} {CONFIG} is a directory (Docker bind-mount artifact). rm -rf it.")
        return 2

    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    problems = 0

    print("Structure:")
    for key in ("architect", "builder", "verifier", "gatekeeper"):
        entry = cfg.get(key)
        if not isinstance(entry, dict):
            print(f"  {BAD} {key}: missing")
            problems += 1
            continue
        aid, akey = entry.get("agent_id") or "", entry.get("api_key") or ""
        if not aid or not akey:
            print(f"  {BAD} {key}: agent_id or api_key is empty")
            problems += 1
            continue
        note = ""
        if not str(akey).startswith("band_a_"):
            note = f"  {WARN} key lacks band_a_ prefix (agent keys are band_a_, user keys band_u_)"
        print(f"  {OK} {key}: {aid}{note}")

    extra = set(cfg) - set(ROLES)
    if extra:
        print(f"  {WARN} unrecognized keys ignored: {sorted(extra)}")

    if problems:
        print(f"\n{problems} role(s) incomplete -- fix before probing.")
        return 1

    print("\nCredentials (GET /api/v1/agent/me):")
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(probe(client, cfg[k]["api_key"]) for k in ROLES)
        )
    for key, (ok, msg) in zip(ROLES, results):
        print(f"  {OK if ok else BAD} {key}: {msg}")
        problems += not ok

    if problems:
        print(f"\n{problems} credential(s) failed.")
        return 1
    print("\nAll four agents authenticate. Next: create a room, add all four, mention @Architect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

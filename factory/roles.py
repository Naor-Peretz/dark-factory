"""Role definitions and the factory's routing topology.

Routing in BAND is deterministic: the mention decides delivery, no model arbitrates.
So the topology below IS the factory's control flow.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    key: str           # agent_config.yaml key
    name: str          # display name used in mentions
    prompt: str        # prompts/<file>
    writes_code: bool  # gets a repo checkout as cwd
    forward_to: str    # default next hop on success
    on_reject: str     # where a rejection goes


ARCHITECT = Role("architect", "Architect", "architect.md", False, "Builder", "Architect")
BUILDER = Role("builder", "Builder", "builder.md", True, "Verifier", "Builder")
VERIFIER = Role("verifier", "Verifier", "verifier.md", True, "Gatekeeper", "Builder")
GATEKEEPER = Role("gatekeeper", "Gatekeeper", "gatekeeper.md", False, "Architect", "Architect")

ROLES = {r.key: r for r in (ARCHITECT, BUILDER, VERIFIER, GATEKEEPER)}

# The cycle. Verifier->Builder on failure is the dependent handoff; Gatekeeper's
# BLOCKED->Architect is the blockable verdict. Both are judging criteria.
TOPOLOGY = """
  human ──@Architect──> plan
  Architect ──@Builder──> code
  Builder ──@Verifier──> evidence
  Verifier ──@Builder──> (on failure: the finding, not the task)
  Verifier ──@Gatekeeper──> (on pass)
  Gatekeeper ──@Architect──> (on BLOCKED)
  Gatekeeper ──SHIP──> done
"""

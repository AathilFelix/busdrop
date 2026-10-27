"""Spark dispatch policy: at each candidate meet (shortfall plus spare
seats), ask Muse Spark which riders to move where, and why.

The LLM proposes; the sim loop routes every proposal through the
verifier before anything moves. Malformed answers and API failures skip
the tick and count as dispatcher errors instead of crashing the run.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .spark import DispatcherError, SparkClient
from .tools import PROPOSE_HANDOFF_SCHEMA, build_messages, get_corridor_state

if TYPE_CHECKING:
    from simulator.sim import Simulation


def spark_policy_factory(client: SparkClient):
    """Build a sim handoff policy driven by a Spark client (or test fake)."""

    def spark_policy(sim: Simulation, bus_id: str, stop_id: str,
                     minute: int) -> list[tuple]:
        state = get_corridor_state(sim, bus_id, stop_id, minute)
        if state["full_bus"]["shortfall"] <= 0 or not state["receivers"]:
            return []
        try:
            proposal: dict[str, Any] = client.propose(
                build_messages(state), PROPOSE_HANDOFF_SCHEMA)
        except DispatcherError:
            sim.result.dispatcher_errors += 1
            return []
        to_bus = proposal.get("to_bus")
        riders = [r for r in proposal.get("rider_ids", [])
                  if isinstance(r, str)]
        explanation = str(proposal.get("explanation", ""))
        if not to_bus or not riders:
            return []
        if to_bus not in {r["bus"] for r in state["receivers"]}:
            sim.result.dispatcher_errors += 1
            return []
        return [(to_bus, riders, explanation)]

    return spark_policy

"""Rider consent: every proposed move is an offer the rider can refuse.

The dispatcher proposes, the verifier authorizes, and then each rider
decides walk/stay. Impatient riders (low patience_min) jump at a roomier
bus; patient riders stay put unless their bus is crush-loaded. The
deterministic rule below is the offline default; a Spark Open client
upgrades each decision to an LLM call with rule fallback on any error.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .open import RiderError

if TYPE_CHECKING:
    from simulator.sim import Simulation

    from .open import SparkOpenClient

SYSTEM_PROMPT = """You are a bus rider in Chennai, already seated on a \
crowded bus that just pulled alongside another bus going to your \
destination. The conductor offers you a free mid-route move: same ticket, \
no extra fare, a short walk across the stop to a bus with spare seats.
Answer with exactly one JSON object: {"walk": true/false, \
"reason": "a few words"}. Walk when the other bus is clearly roomier and \
you dislike the crush; stay when the gain is small or you value your seat. \
Never invent rider or bus ids."""

# Patience at or below this walks whenever the other bus is roomier.
EAGER_PATIENCE = 18
# Patience at or above this never walks: seat lovers.
SEAT_LOVER_PATIENCE = 24
# Crush-loaded source that even patient riders flee.
CRUSH_LOAD = 0.9
# Receiver this full or fuller is never worth the walk.
FULL_LOAD = 0.95


def rule_decision(rider_patience: int, from_load: float,
                  to_load: float) -> bool:
    """Deterministic walk/stay: no RNG, patience already varies per rider."""
    if rider_patience >= SEAT_LOVER_PATIENCE:
        return False
    if to_load >= FULL_LOAD or to_load >= from_load:
        return False
    if rider_patience <= EAGER_PATIENCE:
        return True
    return from_load >= CRUSH_LOAD and to_load <= 0.7


def build_offer(sim: Simulation, rider_id: str, from_bus_id: str,
                to_bus_id: str, stop_id: str, minute: int) -> dict[str, Any]:
    """Snapshot of one offered move for the rider LLM."""
    from_bus = sim.buses[from_bus_id]
    to_bus = sim.buses[to_bus_id]
    rider = sim.riders[rider_id]
    return {
        "minute": minute,
        "stop": stop_id,
        "stop_name": sim.stops[stop_id].name,
        "rider": {"id": rider_id,
                  "destination": rider.destination_id,
                  "patience_min": rider.patience_min},
        "from_bus": {"bus": from_bus_id, "route": from_bus.route_id,
                     "onboard": len(from_bus.onboard),
                     "capacity": from_bus.capacity},
        "to_bus": {"bus": to_bus_id, "route": to_bus.route_id,
                   "onboard": len(to_bus.onboard),
                   "capacity": to_bus.capacity},
    }


def build_messages(offer: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(offer)},
    ]


def rider_policy_factory(client: SparkOpenClient | None = None):
    """Build a sim rider policy: rule-only, or LLM with rule fallback."""

    def rider_policy(sim: Simulation, rider_id: str, from_bus_id: str,
                     to_bus_id: str, stop_id: str, minute: int) -> bool:
        from_bus = sim.buses[from_bus_id]
        to_bus = sim.buses[to_bus_id]
        from_load = len(from_bus.onboard) / from_bus.capacity
        to_load = len(to_bus.onboard) / to_bus.capacity
        patience = sim.riders[rider_id].patience_min
        if client is None:
            return rule_decision(patience, from_load, to_load)
        try:
            offer = build_offer(sim, rider_id, from_bus_id, to_bus_id,
                                stop_id, minute)
            return bool(client.decide(build_messages(offer))["walk"])
        except RiderError:
            sim.result.rider_errors += 1
            return rule_decision(patience, from_load, to_load)

    return rider_policy

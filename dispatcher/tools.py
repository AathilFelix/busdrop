"""Dispatcher tools: get_corridor_state builds the decision snapshot for
one candidate meet; the LLM answers with a propose_handoff tool call,
which the sim routes through the verifier (never direct to execution).
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from simulator.sim import Simulation

PROPOSE_HANDOFF_SCHEMA = {
    "type": "function",
    "function": {
        "name": "propose_handoff",
        "description": (
            "Propose moving riders from the crowded bus to one co-located "
            "bus at the same shared stop. Riders keep their tickets and "
            "destinations; only the bus underneath changes. Pass to_bus "
            "null to skip this meet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to_bus": {
                    "type": ["string", "null"],
                    "description": "Receiver bus id from the candidates, "
                                   "or null to skip.",
                },
                "rider_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Riders to move, from that receiver's "
                                   "eligible list, at most shortfall riders.",
                },
                "explanation": {
                    "type": "string",
                    "description": "One or two plain-language sentences: "
                                   "why this move helps.",
                },
            },
            "required": ["to_bus", "rider_ids", "explanation"],
        },
    },
}

SYSTEM_PROMPT = """You are the BusDrop dispatcher, an AI agent relieving crowded \
city buses. A crowded bus just reached a shared stop with more waiting riders \
than free seats. Other buses from different routes are dwelling at the same \
stop with spare seats.

Answer with exactly one propose_handoff call:
- to_bus: the receiver id, or null to skip when no move helps.
- rider_ids: only ids from that receiver's eligible list, at most \
shortfall riders (moving more than the shortfall just churns riders).
- explanation: one or two plain-language sentences a rider would \
understand.

Never invent bus or rider ids. Prefer the receiver with the most spare \
seats when several work."""


def get_corridor_state(sim: Simulation, bus_id: str, stop_id: str,
                       minute: int) -> dict[str, Any]:
    """Snapshot of one candidate meet for the dispatcher LLM."""
    from simulator.handoff import eligible_waiting

    bus = sim.buses[bus_id]
    waiting = eligible_waiting(sim, bus_id, stop_id)
    shortfall = waiting - (bus.capacity - len(bus.onboard))
    receivers = []
    for other_id in sim.buses_at(stop_id, minute):
        if other_id == bus_id:
            continue
        other = sim.buses[other_id]
        if other.route_id == bus.route_id:
            continue
        spare = other.capacity - len(other.onboard)
        if spare <= 0:
            continue
        downstream = set(sim.routes[other.route_id].downstream_of(stop_id))
        eligible = [{"id": rid,
                     "destination": sim.riders[rid].destination_id}
                    for rid in sorted(bus.onboard)
                    if sim.riders[rid].destination_id in downstream]
        receivers.append({
            "bus": other_id,
            "route": other.route_id,
            "spare_seats": spare,
            "eligible": eligible,
        })
    receivers.sort(key=lambda r: (-r["spare_seats"], r["bus"]))
    return {
        "minute": minute,
        "stop": stop_id,
        "stop_name": sim.stops[stop_id].name,
        "full_bus": {
            "bus": bus_id,
            "route": bus.route_id,
            "onboard": len(bus.onboard),
            "capacity": bus.capacity,
            "waiting": waiting,
            "shortfall": shortfall,
        },
        "receivers": receivers,
    }


def build_messages(state: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(state)},
    ]

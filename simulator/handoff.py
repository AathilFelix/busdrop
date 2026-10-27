"""Handoff mechanics: the deterministic machinery that moves riders between
buses mid-route. No agents here; the dispatcher (phase 4) will drive this
via the verifier (phase 3).

A handoff is all-or-nothing: every precondition is validated before any
state changes, so a rejected proposal leaves the simulation untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sim import Simulation


@dataclass
class HandoffResult:
    ok: bool
    moved: list[str] = field(default_factory=list)
    reason: str = ""


def execute_handoff(
    sim: Simulation,
    from_bus_id: str,
    to_bus_id: str,
    stop_id: str,
    rider_ids: list[str],
    minute: int,
) -> HandoffResult:
    """Move riders from one bus to another at a shared stop.

    Preconditions (all must hold, else nothing changes):
      - both buses exist and differ; the stop exists and is shared
      - both buses are at the stop at this minute (timetable co-location)
      - every rider is onboard the source bus with a valid paid ticket
        for their destination, and the ticket agrees on the current bus
      - every rider's destination is downstream of the stop on the
        receiving bus's route
      - the receiving bus has seats for all of them
    """
    # Dedupe, preserving order, so capacity math can't double-count.
    wanted = list(dict.fromkeys(rider_ids))

    from_bus = sim.buses.get(from_bus_id)
    to_bus = sim.buses.get(to_bus_id)
    stop = sim.stops.get(stop_id)
    if from_bus is None or to_bus is None or stop is None:
        return HandoffResult(False, reason="unknown bus or stop")
    if from_bus_id == to_bus_id:
        return HandoffResult(False, reason="source and receiver are the same bus")
    if not stop.shared:
        return HandoffResult(False, reason=f"stop {stop_id} is not shared")
    if not wanted:
        return HandoffResult(False, reason="no riders requested")
    present = set(sim.buses_at(stop_id, minute))
    if from_bus_id not in present or to_bus_id not in present:
        return HandoffResult(False, reason="buses not co-located at stop")

    to_route = sim.routes[to_bus.route_id]
    downstream = set(to_route.downstream_of(stop_id))
    riders = []
    for rid in wanted:
        rider = sim.riders.get(rid)
        if rider is None or rid not in from_bus.onboard:
            return HandoffResult(False, reason=f"rider {rid} not onboard source bus")
        ticket = rider.ticket
        if (
            ticket is None
            or not ticket.fare_paid
            or ticket.destination_id != rider.destination_id
            or ticket.current_bus != from_bus_id
        ):
            return HandoffResult(False, reason=f"rider {rid} holds no valid ticket")
        if rider.destination_id not in downstream:
            return HandoffResult(
                False,
                reason=f"rider {rid} destination not served downstream by receiver",
            )
        riders.append(rider)

    if len(to_bus.onboard) + len(riders) > to_bus.capacity:
        return HandoffResult(False, reason="receiver lacks spare seats")

    moved = []
    for rider in riders:
        from_bus.onboard.remove(rider.id)
        to_bus.onboard.append(rider.id)
        assert rider.ticket is not None  # validated above
        rider.ticket.current_bus = to_bus_id
        rider.ticket.transfer_history.append((from_bus_id, to_bus_id, stop_id))
        sim.ledger.record(rider.id, from_bus_id, to_bus_id, stop_id, minute)
        moved.append(rider.id)
    to_bus.max_load = max(to_bus.max_load, len(to_bus.onboard))
    return HandoffResult(True, moved=moved)


def _eligible_waiting(sim: Simulation, bus_id: str, stop_id: str) -> int:
    """Waiting riders at a stop whose destination this bus serves."""
    route = sim.routes[sim.buses[bus_id].route_id]
    downstream = set(route.downstream_of(stop_id))
    return sum(1 for r in sim.queues[stop_id]
               if r.destination_id in downstream)


def scripted_policy(
    sim: Simulation, bus_id: str, stop_id: str, minute: int
) -> list[tuple[str, list[str]]]:
    """Deterministic demo driver for the handoff mechanics.

    When more riders wait at a shared stop than the bus has free seats for,
    move just enough onboard riders (whose destinations continue downstream)
    onto the co-located bus with the most spare seats. The trunk queue is
    joint: buses board it in sequence, so front-loading the shortfall bus
    strictly reduces encounters with a full bus this minute; no seats are
    held back for the receiver's "own" queue because it faces only the
    remainder. This is a mechanical test harness, not the agent: the Muse
    Spark dispatcher (phase 4) replaces it.
    """
    bus = sim.buses[bus_id]
    shortfall = _eligible_waiting(sim, bus_id, stop_id) - (
        bus.capacity - len(bus.onboard))
    if shortfall <= 0:
        return []
    candidates = []
    for other_id in sim.buses_at(stop_id, minute):
        if other_id == bus_id:
            continue
        other = sim.buses[other_id]
        if other.route_id == bus.route_id:
            continue
        spare = other.capacity - len(other.onboard)
        if spare > 0:
            candidates.append((other_id, spare))
    if not candidates:
        return []
    candidates.sort(key=lambda c: (-c[1], c[0]))
    to_bus_id, spare = candidates[0]

    downstream = set(sim.routes[sim.buses[to_bus_id].route_id].downstream_of(stop_id))
    eligible = sorted(
        rid
        for rid in bus.onboard
        if sim.riders[rid].destination_id in downstream
    )
    if not eligible:
        return []
    return [(to_bus_id, eligible[:min(shortfall, spare)])]

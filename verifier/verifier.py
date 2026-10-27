"""Deterministic safety layer: every handoff proposal is approved or
rejected here before any rider moves.

The agent proposes, the verifier authorizes, the ledger executes. Unlike
execute_handoff (fail-fast execution guard), verify() reports EVERY failed
check so the agent gets a full diagnosis. Unlike execute_handoff (exact
co-location), the ETA check allows a small window: the verifier judges
whether a proposal is timely, the mechanics judge whether it is
physically possible right now.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.sim import Simulation

ETA_WINDOW_MIN = 5  # buses must dwell at the stop within ±5 min of proposal


@dataclass(frozen=True)
class Proposal:
    from_bus: str
    to_bus: str
    stop_id: str
    rider_ids: tuple[str, ...]
    minute: int


@dataclass
class Verdict:
    approved: bool
    failures: list[str] = field(default_factory=list)


def check_entities(sim: Simulation, p: Proposal) -> list[str]:
    """Structural validity: known buses/stop/riders, distinct buses,
    shared stop, non-empty list, riders onboard the source."""
    failures = []
    from_bus = sim.buses.get(p.from_bus)
    to_bus = sim.buses.get(p.to_bus)
    stop = sim.stops.get(p.stop_id)
    if from_bus is None:
        failures.append(f"unknown source bus {p.from_bus}")
    if to_bus is None:
        failures.append(f"unknown receiver bus {p.to_bus}")
    if stop is None:
        failures.append(f"unknown stop {p.stop_id}")
    if p.from_bus == p.to_bus:
        failures.append("source and receiver are the same bus")
    if stop is not None and not stop.shared:
        failures.append(f"stop {p.stop_id} is not shared")
    if not p.rider_ids:
        failures.append("no riders proposed")
    if from_bus is not None:
        for rid in p.rider_ids:
            rider = sim.riders.get(rid)
            if rider is None:
                failures.append(f"unknown rider {rid}")
            elif rid not in from_bus.onboard:
                failures.append(f"rider {rid} not onboard source bus")
    return failures


def check_destination(sim: Simulation, p: Proposal) -> list[str]:
    """Both buses serve every rider's destination downstream of the stop."""
    failures = []
    downs: dict[str, set[str]] = {}
    for label, bus_id in (("source", p.from_bus), ("receiver", p.to_bus)):
        route = sim.routes[sim.buses[bus_id].route_id]
        if p.stop_id not in route.stop_ids:
            failures.append(f"{label} bus {bus_id} does not serve "
                            f"stop {p.stop_id}")
            return failures
        downs[label] = set(route.downstream_of(p.stop_id))
    for rid in p.rider_ids:
        dest = sim.riders[rid].destination_id
        if dest not in downs["source"]:
            failures.append(f"rider {rid} destination {dest} not downstream "
                            f"of {p.stop_id} on source route")
        if dest not in downs["receiver"]:
            failures.append(f"rider {rid} destination {dest} not served "
                            f"downstream of {p.stop_id} by receiver")
    return failures


def check_eta_window(sim: Simulation, p: Proposal) -> list[str]:
    """Both buses dwell at the stop within ±ETA_WINDOW_MIN of proposal."""
    failures = []
    for label, bus_id in (("source", p.from_bus), ("receiver", p.to_bus)):
        dwells = sim.dwells_at(bus_id, p.stop_id)
        if not dwells:
            failures.append(f"{label} bus {bus_id} never dwells "
                            f"at {p.stop_id}")
        else:
            nearest = min(dwells, key=lambda m: abs(m - p.minute))
            if abs(nearest - p.minute) > ETA_WINDOW_MIN:
                failures.append(
                    f"{label} bus {bus_id} nearest dwell at {p.stop_id} "
                    f"is t={nearest}, outside ±{ETA_WINDOW_MIN} "
                    f"of t={p.minute}")
    return failures


def check_capacity(sim: Simulation, p: Proposal) -> list[str]:
    """The receiver fits every proposed rider."""
    to_bus = sim.buses[p.to_bus]
    need = len(set(p.rider_ids))
    spare = to_bus.capacity - len(to_bus.onboard)
    if spare < need:
        return [f"receiver {p.to_bus} has {spare} spare seats "
                f"for {need} riders"]
    return []


def check_tickets(sim: Simulation, p: Proposal) -> list[str]:
    """Every rider holds a valid paid ticket for this move."""
    failures = []
    for rid in p.rider_ids:
        rider = sim.riders[rid]
        t = rider.ticket
        if t is None:
            reason = "has no ticket"
        elif not t.fare_paid:
            reason = "ticket unpaid"
        elif t.destination_id != rider.destination_id:
            reason = "ticket destination mismatch"
        elif t.current_bus != p.from_bus:
            reason = f"ticket is on {t.current_bus}"
        else:
            continue
        failures.append(f"rider {rid} {reason}")
    return failures


RULE_CHECKS = (check_destination, check_eta_window, check_capacity,
               check_tickets)


def verify(sim: Simulation, p: Proposal) -> Verdict:
    """Approve only if every check passes; collect all failures."""
    structural = check_entities(sim, p)
    if structural:
        return Verdict(approved=False, failures=structural)
    failures: list[str] = []
    for check in RULE_CHECKS:
        failures.extend(check(sim, p))
    return Verdict(approved=not failures, failures=failures)

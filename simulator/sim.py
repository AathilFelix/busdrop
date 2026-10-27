"""Timestep corridor simulation. Baseline mode: buses run their routes and
riders board the first bus serving their destination; no handoffs.

Phase 2 adds an optional handoff policy hook: at each shared-stop event,
after alighting and before boarding, the policy may request handoffs that
are executed through the validated execute_handoff machinery.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .handoff import execute_handoff
from .ledger import TicketLedger
from .models import Bus, Rider, Route, Stop, Ticket
from .network import DWELL_MIN, LEG_MIN

COOLDOWN_MIN = 40  # extra minutes after arrivals stop so buses finish trips

# (sim, bus_id, stop_id, minute) -> [(to_bus_id, [rider_ids])].
HandoffPolicy = Callable[
    ["Simulation", str, str, int], list[tuple[str, list[str]]]
]


@dataclass
class SimResult:
    total_riders: int = 0
    boarded: int = 0
    alighted: int = 0
    onboard_at_end: int = 0
    unserved: int = 0
    denied_boardings: int = 0
    avg_wait_min: float = 0.0
    peak_load_factor: float = 0.0
    handoff_events: int = 0
    riders_transferred: int = 0
    boardings_by_route: dict[str, int] = field(default_factory=dict)
    denied_by_route: dict[str, int] = field(default_factory=dict)
    peak_load_by_route: dict[str, float] = field(default_factory=dict)
    avg_load_by_route: dict[str, float] = field(default_factory=dict)
    max_load_by_bus: dict[str, int] = field(default_factory=dict)


class Simulation:
    def __init__(
        self,
        stops: dict[str, Stop],
        routes: dict[str, Route],
        buses: list[Bus],
        riders: list[Rider],
        minutes: int,
        handoff_policy: HandoffPolicy | None = None,
    ) -> None:
        self.stops = stops
        self.routes = routes
        self.buses = {b.id: b for b in buses}
        self.riders = {r.id: r for r in riders}
        self.minutes = minutes
        self.handoff_policy = handoff_policy
        self.ledger = TicketLedger()
        self._events = self._timetable()
        self._meet_counter = 0
        self.queues: dict[str, list[Rider]] = {sid: [] for sid in stops}
        self._arrivals = sorted(riders, key=lambda r: (r.arrival_min, r.id))
        self.result = SimResult(
            total_riders=len(riders),
            boardings_by_route={rid: 0 for rid in routes},
            denied_by_route={rid: 0 for rid in routes},
            peak_load_by_route={rid: 0.0 for rid in routes},
            avg_load_by_route={rid: 0.0 for rid in routes},
        )
        self._load_samples: dict[str, list[float]] = {
            rid: [] for rid in routes}

    def _timetable(self) -> dict[int, list[tuple[str, str]]]:
        """Precompute minute -> [(bus_id, stop_id)] arrival events."""
        events: dict[int, list[tuple[str, str]]] = {}
        horizon = self.minutes + COOLDOWN_MIN
        for bus in self.buses.values():
            stops = self.routes[bus.route_id].stop_ids
            for i, stop_id in enumerate(stops):
                t = bus.start_min + i * (DWELL_MIN + LEG_MIN)
                if t < horizon:
                    events.setdefault(t, []).append((bus.id, stop_id))
        return events

    def buses_at(self, stop_id: str, minute: int) -> list[str]:
        """Bus ids dwelling at a stop at a minute, in timetable order."""
        return [bid for bid, sid in self._events.get(minute, [])
                if sid == stop_id]

    def _process_stop(self, bus: Bus, stop_id: str, minute: int) -> None:
        route = self.routes[bus.route_id]
        res = self.result

        for rid in list(bus.onboard):
            rider = self.riders[rid]
            if rider.destination_id == stop_id:
                rider.alight_min = minute
                bus.onboard.remove(rid)
                res.alighted += 1

        if stop_id == route.stop_ids[-1]:
            return  # terminus: nobody boards

        if self.handoff_policy is not None and self.stops[stop_id].shared:
            requests = self.handoff_policy(self, bus.id, stop_id, minute) or []
            for to_bus_id, rider_ids in requests:
                result = execute_handoff(
                    self, bus.id, to_bus_id, stop_id, rider_ids, minute)
                if result.ok:
                    res.handoff_events += 1
                    res.riders_transferred += len(result.moved)

        downstream = set(route.downstream_of(stop_id))
        queue = self.queues[stop_id]
        for rider in list(queue):
            if rider.destination_id not in downstream:
                continue
            if len(bus.onboard) >= bus.capacity:
                res.denied_boardings += 1
                res.denied_by_route[bus.route_id] += 1
                continue
            rider.board_min = minute
            rider.ticket = Ticket(
                rider_id=rider.id,
                destination_id=rider.destination_id,
                issued_by_bus=bus.id,
                current_bus=bus.id,
            )
            bus.onboard.append(rider.id)
            queue.remove(rider)
            res.boarded += 1
            res.boardings_by_route[bus.route_id] += 1

        bus.max_load = max(bus.max_load, len(bus.onboard))
        load = len(bus.onboard) / bus.capacity
        res.peak_load_factor = max(res.peak_load_factor, load)
        res.peak_load_by_route[bus.route_id] = max(
            res.peak_load_by_route[bus.route_id], load)
        self._load_samples[bus.route_id].append(load)

    def _ordered_events(self, minute: int) -> list[tuple[str, str]]:
        """Meet events with per-stop boarding order rotated fairly.

        Co-located buses serve one joint queue in sequence. Fixed timetable
        order would starve the last route (it always faces an empty queue),
        so each meet rotates which route boards first. Deterministic: the
        counter advances once per multi-bus stop event.
        """
        events = self._events.get(minute, [])
        by_stop: dict[str, list[str]] = {}
        for bus_id, stop_id in events:
            by_stop.setdefault(stop_id, []).append(bus_id)
        ordered = []
        for stop_id, bus_ids in by_stop.items():
            if len(bus_ids) > 1:
                k = self._meet_counter % len(bus_ids)
                self._meet_counter += 1
                bus_ids = bus_ids[k:] + bus_ids[:k]
            ordered.extend((bid, stop_id) for bid in bus_ids)
        return ordered

    def run(self) -> SimResult:
        res = self.result
        upcoming = list(self._arrivals)
        for minute in range(self.minutes + COOLDOWN_MIN):
            while upcoming and upcoming[0].arrival_min <= minute:
                rider = upcoming.pop(0)
                self.queues[rider.origin_id].append(rider)
            for bus_id, stop_id in self._ordered_events(minute):
                self._process_stop(self.buses[bus_id], stop_id, minute)

        waits = [r.board_min - r.arrival_min for r in self.riders.values()
                 if r.board_min is not None]
        res.avg_wait_min = sum(waits) / len(waits) if waits else 0.0
        res.onboard_at_end = sum(1 for r in self.riders.values()
                                 if r.board_min is not None
                                 and r.alight_min is None)
        res.unserved = sum(1 for r in self.riders.values()
                           if r.board_min is None)
        res.max_load_by_bus = {b.id: b.max_load for b in self.buses.values()}
        for rid, samples in self._load_samples.items():
            res.avg_load_by_route[rid] = (
                sum(samples) / len(samples) if samples else 0.0)
        return res


def run_baseline(
    stops: dict[str, Stop],
    routes: dict[str, Route],
    buses: list[Bus],
    riders: list[Rider],
    minutes: int,
) -> SimResult:
    return Simulation(stops, routes, buses, riders, minutes).run()

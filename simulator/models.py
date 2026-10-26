"""Core data model for the BusDrop corridor simulator."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stop:
    id: str
    name: str
    shared: bool  # True if on the shared Anna Salai trunk


@dataclass
class Route:
    id: str
    name: str
    stop_ids: list[str]

    def downstream_of(self, stop_id: str) -> list[str]:
        idx = self.stop_ids.index(stop_id)
        return self.stop_ids[idx + 1:]


@dataclass
class Ticket:
    """A ticket belongs to a destination, not to a bus.

    Issued on boarding. fare_paid carries over if the rider later moves to
    another bus; transfer machinery arrives in phase 2 with the TicketLedger.
    """

    rider_id: str
    destination_id: str
    fare_paid: bool = True
    issued_by_bus: str | None = None
    current_bus: str | None = None
    transfer_history: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class Rider:
    id: str
    origin_id: str
    destination_id: str
    arrival_min: int  # minute the rider reaches the stop
    patience_min: int  # stored now; drives rider-agent decisions in phase 5
    ticket: Ticket | None = None
    board_min: int | None = None
    alight_min: int | None = None


@dataclass
class Bus:
    id: str
    route_id: str
    capacity: int
    start_min: int  # departure minute from the origin stop
    onboard: list[str] = field(default_factory=list)  # rider ids
    max_load: int = 0

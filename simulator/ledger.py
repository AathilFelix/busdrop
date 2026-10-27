"""Ticket synchronization layer: a single in-memory ledger recording every
mid-route rider transfer.

The ticket belongs to the destination, not to the bus. When a rider moves
from bus A to bus B, no new fare is collected; the ledger entry is the
proof bus B needs that the rider already paid. In a real deployment this
would be a shared backend or a QR re-scan; in the simulator it is one
shared registry owned by the Simulation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transfer:
    rider_id: str
    from_bus: str
    to_bus: str
    stop_id: str
    minute: int


class TicketLedger:
    """Append-only record of handoffs. Written only by execute_handoff."""

    def __init__(self) -> None:
        self.transfers: list[Transfer] = []

    def record(
        self,
        rider_id: str,
        from_bus: str,
        to_bus: str,
        stop_id: str,
        minute: int,
    ) -> Transfer:
        transfer = Transfer(rider_id, from_bus, to_bus, stop_id, minute)
        self.transfers.append(transfer)
        return transfer

    def transfers_for_rider(self, rider_id: str) -> list[Transfer]:
        return [t for t in self.transfers if t.rider_id == rider_id]

    def transfers_at_stop(self, stop_id: str) -> list[Transfer]:
        return [t for t in self.transfers if t.stop_id == stop_id]

    def __len__(self) -> int:
        return len(self.transfers)

"""Morning-peak rider demand: time-varying arrivals at each stop, with
destinations weighted toward the Broadway end of the trunk."""
from __future__ import annotations

import math
import random

from .models import Rider, Route, Stop

PEAK_MIN = 105  # demand peaks 105 min into the window (08:45 for a 07:00 start)
PEAK_WIDTH = 28.0
BASE_SHARE = 0.25  # off-peak rate as a share of the peak rate

# Riders per minute at each stop at the height of the peak. Royapettah is
# the hot branch (fills its buses from branch boardings alone at peak),
# Gemini the quiet one, so overflow and spare capacity coexist on the
# same trunk.
STOP_PEAK_RATE = {
    "ROY": 1.6,
    "PYC": 1.0,
    "TEY": 0.9,
    "SIE": 0.6,
    "GEM": 0.45,
    "THL": 1.3,
    "LIC": 1.0,
    "SIM": 0.7,
    "CEN": 0.5,
    "BWY": 0.0,  # terminus: nobody boards
}

# Destination preference weights; filtered to stops downstream of the
# rider's origin and renormalized.
DEST_WEIGHT = {
    "PYC": 0.05,
    "SIE": 0.05,
    "THL": 0.08,
    "LIC": 0.10,
    "SIM": 0.12,
    "CEN": 0.20,
    "BWY": 0.45,
}


def rate_at(stop_id: str, minute: int) -> float:
    peak = STOP_PEAK_RATE[stop_id]
    bump = math.exp(-((minute - PEAK_MIN) / PEAK_WIDTH) ** 2)
    return peak * (BASE_SHARE + (1.0 - BASE_SHARE) * bump)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    threshold = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= threshold:
            return k - 1


def _pick_destination(
    rng: random.Random, routes: dict[str, Route], origin_id: str,
) -> str:
    downstream: list[str] = []
    for route in routes.values():
        if origin_id in route.stop_ids:
            for sid in route.downstream_of(origin_id):
                if sid not in downstream:
                    downstream.append(sid)
    weights = [DEST_WEIGHT[sid] for sid in downstream]
    return rng.choices(downstream, weights=weights, k=1)[0]


def generate_riders(
    stops: dict[str, Stop],
    routes: dict[str, Route],
    minutes: int,
    seed: int = 42,
    scale: float = 1.0,
) -> list[Rider]:
    """Pre-generate every rider in the window; the sim reveals them by
    arrival_min. Deterministic for a given seed."""
    rng = random.Random(seed)
    riders: list[Rider] = []
    n = 0
    for minute in range(minutes):
        for stop_id in stops:
            count = _poisson(rng, rate_at(stop_id, minute) * scale)
            for _ in range(count):
                n += 1
                riders.append(Rider(
                    id=f"P{n}",
                    origin_id=stop_id,
                    destination_id=_pick_destination(rng, routes, stop_id),
                    arrival_min=minute,
                    patience_min=rng.randint(10, 25),
                ))
    riders.sort(key=lambda r: (r.arrival_min, r.id))
    return riders

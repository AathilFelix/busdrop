"""Chennai corridor network: Royapettah, Teynampet and Gemini routes
converging on the shared Anna Salai trunk into Broadway."""
from __future__ import annotations

from .models import Bus, Route, Stop

LEG_MIN = 4  # travel time between consecutive stops
DWELL_MIN = 1  # dwell time at each stop

# Trunk stops are served by all three routes, in the same order.
_TRUNK = ["THL", "LIC", "SIM", "CEN", "BWY"]


def build_stops() -> dict[str, Stop]:
    names = {
        "ROY": "Royapettah",
        "PYC": "Pycrofts Road",
        "TEY": "Teynampet",
        "SIE": "SIET",
        "GEM": "Gemini",
        "THL": "Thousand Lights",
        "LIC": "LIC",
        "SIM": "Simpson",
        "CEN": "Central",
        "BWY": "Broadway",
    }
    return {
        sid: Stop(id=sid, name=name, shared=sid in _TRUNK)
        for sid, name in names.items()
    }


def build_routes() -> dict[str, Route]:
    return {
        "R1": Route(id="R1", name="Royapettah - Broadway",
                    stop_ids=["ROY", "PYC"] + _TRUNK),
        "R2": Route(id="R2", name="Teynampet - Broadway",
                    stop_ids=["TEY", "SIE"] + _TRUNK),
        "R3": Route(id="R3", name="Gemini - Broadway",
                    stop_ids=["GEM"] + _TRUNK),
    }


def build_buses(
    routes: dict[str, Route],
    buses_per_route: int = 10,
    capacity: int = 40,
    first_departure: int = 0,
    headway: int = 20,
) -> list[Bus]:
    buses = []
    for route_id in sorted(routes):
        for i in range(buses_per_route):
            buses.append(Bus(
                id=f"{route_id}-B{i + 1}",
                route_id=route_id,
                capacity=capacity,
                start_min=first_departure + i * headway,
            ))
    return buses


def build_corridor(
    buses_per_route: int = 10,
    capacity: int = 40,
    first_departure: int = 0,
    headway: int = 20,
) -> tuple[dict[str, Stop], dict[str, Route], list[Bus]]:
    stops = build_stops()
    routes = build_routes()
    buses = build_buses(routes, buses_per_route, capacity,
                        first_departure, headway)
    return stops, routes, buses

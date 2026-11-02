"""Local API serving simulation runs to the Next.js frontend in web/.

Run from the repo root:

    .venv/bin/uvicorn api:app --port 8000

The frontend reaches it through web/app/api/* route handlers (same
origin for the browser). Response shapes mirror dashboard/app.py's
run_recorded: same engine, same numbers.
"""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dispatcher.spark import DispatcherError, resolve_api_key
from simulator.demand import generate_riders
from simulator.handoff import reckless_policy, scripted_policy
from simulator.network import STOP_COORDS, build_corridor, build_routes, build_stops
from simulator.sim import Simulation

MINUTES = 180
START_HOUR = 7  # the simulated morning starts at 07:00

SCENARIOS = [
    {"id": "morning", "label": "Morning rush", "seed": 42},
    {"id": "festival", "label": "Festival crowd", "seed": 7},
    {"id": "rainy", "label": "Rainy Monday", "seed": 123},
]
ROUTE_SHORT = {"R1": "Royapettah", "R2": "Teynampet", "R3": "Gemini"}

app = FastAPI(title="BusDrop API")


@app.get("/")
def index() -> dict:
    return {"service": "busdrop", "docs": "/docs"}


@app.get("/api/health")
def health() -> dict:
    try:
        resolve_api_key()
        spark = True
    except DispatcherError:
        spark = False
    return {"ok": True, "spark": spark}


@app.get("/api/corridor")
def corridor() -> dict:
    stops = build_stops()
    routes = build_routes()
    return {
        "minutes": MINUTES,
        "start_hour": START_HOUR,
        "scenarios": SCENARIOS,
        "stops": {
            sid: {"name": s.name, "shared": s.shared,
                  "lat": STOP_COORDS[sid][0], "lon": STOP_COORDS[sid][1]}
            for sid, s in stops.items()
        },
        "routes": {
            rid: {"name": r.name, "short": ROUTE_SHORT.get(rid, rid),
                  "stop_ids": r.stop_ids}
            for rid, r in routes.items()
        },
    }


class RunRequest(BaseModel):
    seed: int = 42
    dispatcher: Literal["baseline", "scripted", "reckless", "spark"] = "scripted"
    riders: bool = True
    voice: bool = True


def _slim_frames(frames: list[dict]) -> list[dict]:
    """Round coords to cut payload weight; shape stays dashboard-identical."""
    slimmed = []
    for f in frames:
        slimmed.append({
            "minute": f["minute"],
            "buses": {
                bid: {"route": b["route"],
                      "lat": round(b["lat"], 5), "lon": round(b["lon"], 5),
                      "onboard": b["onboard"], "capacity": b["capacity"],
                      "start": b["start"]}
                for bid, b in f["buses"].items()
            },
            "queues": f["queues"],
            "denied": f["denied"],
            "handoffs": f["handoffs"],
        })
    return slimmed


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    stops, routes, buses = build_corridor()
    riders = generate_riders(stops, routes, MINUTES, seed=req.seed)

    policy = None
    if req.dispatcher == "spark":
        from dispatcher import (DispatcherError, SparkClient,
                                spark_policy_factory)
        try:
            client = SparkClient()
        except DispatcherError as e:
            raise HTTPException(status_code=502, detail=str(e))
        policy = spark_policy_factory(client)
    elif req.dispatcher == "scripted":
        policy = scripted_policy
    elif req.dispatcher == "reckless":
        policy = reckless_policy

    rider_policy = None
    if req.riders and policy is not None:
        from riders import rider_policy_factory
        rider_policy = rider_policy_factory()
    voice_feed = None
    if req.voice and policy is not None:
        from voice import load_demo
        voice_feed = load_demo()

    sim = Simulation(stops, routes, buses, riders, MINUTES,
                     handoff_policy=policy, record=True,
                     rider_policy=rider_policy, voice_feed=voice_feed)
    res = sim.run()
    moves = [{"minute": f["minute"], **h}
             for f in sim.frames for h in f["handoffs"]]
    log = []
    for e in sim.dispatcher_log:
        declined = set(e.get("declined_ids", []))
        dests = sorted({sim.riders[rid].destination_id
                        for rid in e["rider_ids"]
                        if rid not in declined and rid in sim.riders})
        log.append({**e, "destinations": dests})
    voice = []
    if voice_feed is not None:
        voice = [{"minute": s.minute, "text": s.text,
                  "language": s.language, "level": s.level,
                  "stop_id": s.stop_id} for s in voice_feed.signals]
    return {
        "result": {
            "total": res.total_riders, "boarded": res.boarded,
            "alighted": res.alighted, "unserved": res.unserved,
            "denied": res.denied_boardings, "wait": res.avg_wait_min,
            "peak": res.peak_load_factor, "events": res.handoff_events,
            "moved": res.riders_transferred,
            "approved": res.verifier_approvals,
            "rejected": res.verifier_rejections,
            "offers": res.rider_offers, "declines": res.rider_declines,
            "denied_by_route": dict(res.denied_by_route),
            "avg_load_by_route": dict(res.avg_load_by_route),
            "peak_load_by_route": dict(res.peak_load_by_route),
        },
        "frames": _slim_frames(sim.frames),
        "moves": moves,
        "voice": voice,
        "log": log,
    }

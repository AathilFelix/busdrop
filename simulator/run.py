"""CLI entry point: python -m simulator.run --no-handoff [--seed 42]."""
from __future__ import annotations

import argparse
import sys

from .demand import generate_riders
from .network import build_corridor
from .sim import SimResult, run_baseline


def print_report(res: SimResult, seed: int, minutes: int) -> None:
    print(f"BusDrop baseline run (no handoff) - seed={seed}, "
          f"window={minutes} min")
    print(f"  Riders: {res.total_riders} total | {res.boarded} boarded | "
          f"{res.alighted} alighted | {res.unserved} unserved")
    print(f"  Denied boardings (left-behind events): {res.denied_boardings}")
    print(f"  Avg wait: {res.avg_wait_min:.1f} min")
    print(f"  Peak load factor: {res.peak_load_factor:.2f}")
    print("  Per route:")
    for rid in sorted(res.boardings_by_route):
        print(f"    {rid}: boarded={res.boardings_by_route[rid]} "
              f"denied={res.denied_by_route[rid]} "
              f"peak_load={res.peak_load_by_route[rid]:.2f} "
              f"avg_load={res.avg_load_by_route[rid]:.2f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BusDrop corridor simulator")
    parser.add_argument("--no-handoff", action="store_true",
                        help="baseline mode: no handoffs (default)")
    parser.add_argument("--dispatcher", metavar="AGENT",
                        help="agentic dispatcher (arrives in phase 4)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minutes", type=int, default=180)
    parser.add_argument("--demand-scale", type=float, default=1.0,
                        help="multiply all arrival rates (sensitivity tests)")
    args = parser.parse_args(argv)

    if args.dispatcher is not None:
        print(f"error: --dispatcher {args.dispatcher} arrives in phase 4; "
              "phase 1 runs the baseline only", file=sys.stderr)
        return 2

    stops, routes, buses = build_corridor()
    riders = generate_riders(stops, routes, args.minutes,
                             seed=args.seed, scale=args.demand_scale)
    res = run_baseline(stops, routes, buses, riders, args.minutes)
    print_report(res, args.seed, args.minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())

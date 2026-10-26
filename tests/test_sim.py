"""Phase 1 simulator checks: determinism, rider conservation, capacity
limits, ticket issuance, and demand sensitivity. Stdlib unittest only."""
import unittest

from simulator.demand import generate_riders
from simulator.network import build_corridor
from simulator.sim import Simulation


def fresh_run(seed=42, scale=1.0, minutes=180):
    stops, routes, buses = build_corridor()
    riders = generate_riders(stops, routes, minutes, seed=seed, scale=scale)
    sim = Simulation(stops, routes, buses, riders, minutes)
    return sim, sim.run()


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_metrics(self):
        _, a = fresh_run(seed=42)
        _, b = fresh_run(seed=42)
        self.assertEqual(a.total_riders, b.total_riders)
        self.assertEqual(a.boarded, b.boarded)
        self.assertEqual(a.denied_boardings, b.denied_boardings)
        self.assertEqual(a.unserved, b.unserved)
        self.assertAlmostEqual(a.avg_wait_min, b.avg_wait_min)
        self.assertEqual(a.boardings_by_route, b.boardings_by_route)
        self.assertEqual(a.max_load_by_bus, b.max_load_by_bus)


class TestConservation(unittest.TestCase):
    def test_every_rider_accounted_for(self):
        sim, res = fresh_run(seed=42)
        riders = list(sim.riders.values())
        self.assertEqual(res.total_riders, len(riders))
        self.assertEqual(res.boarded + res.unserved, res.total_riders)
        self.assertEqual(res.alighted + res.onboard_at_end, res.boarded)
        for r in riders:
            if r.board_min is not None:
                self.assertGreaterEqual(r.board_min, r.arrival_min)
            if r.alight_min is not None:
                self.assertGreaterEqual(r.alight_min, r.board_min)

    def test_capacity_never_exceeded(self):
        _, res = fresh_run(seed=42)
        for bus_id, max_load in res.max_load_by_bus.items():
            self.assertLessEqual(max_load, 40, bus_id)

    def test_destinations_are_downstream(self):
        stops, routes, _ = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=7)
        serving = {}
        for rid, route in routes.items():
            for sid in route.stop_ids:
                serving.setdefault(sid, []).append(route)
        for r in riders:
            ok = any(r.destination_id in rt.downstream_of(r.origin_id)
                     for rt in serving[r.origin_id])
            self.assertTrue(ok, r)

    def test_boarded_riders_hold_paid_tickets(self):
        sim, _ = fresh_run(seed=42)
        for r in sim.riders.values():
            if r.board_min is not None:
                self.assertIsNotNone(r.ticket, r.id)
                self.assertTrue(r.ticket.fare_paid, r.id)
                self.assertEqual(r.ticket.destination_id,
                                 r.destination_id, r.id)
                self.assertIsNotNone(r.ticket.current_bus, r.id)


class TestDemandSensitivity(unittest.TestCase):
    def test_more_demand_never_less_pain(self):
        _, base = fresh_run(seed=42, scale=1.0)
        _, hot = fresh_run(seed=42, scale=2.0)
        self.assertGreater(hot.total_riders, base.total_riders)
        self.assertGreaterEqual(hot.denied_boardings, base.denied_boardings)
        self.assertGreaterEqual(hot.avg_wait_min, base.avg_wait_min - 1e-9)

    def test_overflow_exists_at_default_demand(self):
        _, res = fresh_run(seed=42)
        self.assertGreater(res.denied_boardings, 0)
        self.assertEqual(res.peak_load_factor, 1.0)


if __name__ == "__main__":
    unittest.main()

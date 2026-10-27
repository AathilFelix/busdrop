"""Phase 2 checks: ledger + handoff mechanics, the scripted demo policy,
and scripted-vs-baseline integration. Stdlib unittest only."""
import unittest

from simulator.demand import generate_riders
from simulator.handoff import execute_handoff, scripted_policy
from simulator.models import Bus, Rider, Route, Stop, Ticket
from simulator.network import build_corridor
from simulator.sim import Simulation


def board(sim, rider, bus_id, minute=0):
    rider.board_min = minute
    rider.ticket = Ticket(
        rider_id=rider.id,
        destination_id=rider.destination_id,
        issued_by_bus=bus_id,
        current_bus=bus_id,
    )
    sim.buses[bus_id].onboard.append(rider.id)


def tiny_world(cap_a=2, cap_b=2, b_start=0):
    """Two routes (RA: X-S-Y, RB: Z-S-Y) meeting at shared stop S.

    A1 and B1 dwell at S at minute 5 when b_start=0; b_start=1 breaks
    the meet. Riders r1/r2 (X->Y) start onboard A1 with paid tickets.
    """
    stops = {
        "X": Stop(id="X", name="Branch A", shared=False),
        "Z": Stop(id="Z", name="Branch B", shared=False),
        "S": Stop(id="S", name="Shared", shared=True),
        "Y": Stop(id="Y", name="End", shared=False),
    }
    routes = {
        "RA": Route(id="RA", name="A", stop_ids=["X", "S", "Y"]),
        "RB": Route(id="RB", name="B", stop_ids=["Z", "S", "Y"]),
    }
    buses = [
        Bus(id="A1", route_id="RA", capacity=cap_a, start_min=0),
        Bus(id="B1", route_id="RB", capacity=cap_b, start_min=b_start),
    ]
    riders = [
        Rider(id="r1", origin_id="X", destination_id="Y",
              arrival_min=0, patience_min=15),
        Rider(id="r2", origin_id="X", destination_id="Y",
              arrival_min=0, patience_min=15),
    ]
    sim = Simulation(stops, routes, buses, riders, minutes=20)
    for r in riders:
        board(sim, r, "A1")
    return sim


class TestExecuteHandoff(unittest.TestCase):
    def test_success_moves_riders_and_records(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 5)
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(res.moved, ["r1"])
        self.assertEqual(sim.buses["A1"].onboard, ["r2"])
        self.assertEqual(sim.buses["B1"].onboard, ["r1"])
        self.assertEqual(len(sim.ledger), 1)
        t = sim.ledger.transfers[0]
        self.assertEqual(
            (t.rider_id, t.from_bus, t.to_bus, t.stop_id, t.minute),
            ("r1", "A1", "B1", "S", 5),
        )

    def test_ticket_keeps_destination_not_bus(self):
        sim = tiny_world()
        ticket_before = sim.riders["r1"].ticket
        res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 5)
        self.assertTrue(res.ok, res.reason)
        ticket = sim.riders["r1"].ticket
        self.assertIs(ticket, ticket_before)  # same ticket, not reissued
        self.assertEqual(ticket.destination_id, "Y")
        self.assertTrue(ticket.fare_paid)  # no extra fare
        self.assertEqual(ticket.issued_by_bus, "A1")
        self.assertEqual(ticket.current_bus, "B1")
        self.assertEqual(ticket.transfer_history, [("A1", "B1", "S")])

    def test_atomic_reject_leaves_state_untouched(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "B1", "S", ["r1", "ghost"], 5)
        self.assertFalse(res.ok)
        self.assertTrue(res.reason)
        self.assertEqual(res.moved, [])
        self.assertEqual(sim.buses["A1"].onboard, ["r1", "r2"])
        self.assertEqual(sim.buses["B1"].onboard, [])
        self.assertEqual(len(sim.ledger), 0)
        self.assertEqual(
            sim.riders["r1"].ticket.transfer_history, [])

    def test_rejects_non_shared_stop(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "B1", "X", ["r1"], 0)
        self.assertFalse(res.ok)
        self.assertIn("not shared", res.reason)

    def test_rejects_unknown_entities(self):
        sim = tiny_world()
        for args in [("ZZ", "B1", "S", ["r1"]),
                     ("A1", "ZZ", "S", ["r1"]),
                     ("A1", "B1", "ZZ", ["r1"])]:
            res = execute_handoff(sim, *args, 5)
            self.assertFalse(res.ok, args)
            self.assertIn("unknown", res.reason)

    def test_rejects_same_bus(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "A1", "S", ["r1"], 5)
        self.assertFalse(res.ok)

    def test_rejects_empty_list(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "B1", "S", [], 5)
        self.assertFalse(res.ok)

    def test_rejects_not_colocated(self):
        sim = tiny_world(b_start=1)
        self.assertEqual(sim.buses_at("S", 5), ["A1"])
        res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 5)
        self.assertFalse(res.ok)
        self.assertIn("co-located", res.reason)
        self.assertEqual(len(sim.ledger), 0)

    def test_rejects_rider_not_onboard(self):
        sim = tiny_world()
        stray = Rider(id="r3", origin_id="X", destination_id="Y",
                      arrival_min=0, patience_min=15)
        sim.riders["r3"] = stray
        res = execute_handoff(sim, "A1", "B1", "S", ["r3"], 5)
        self.assertFalse(res.ok)
        self.assertIn("not onboard", res.reason)

    def test_rejects_destination_not_downstream(self):
        sim = tiny_world()
        # r3 rides A1 as far as S itself; S is not downstream of S on RB.
        sim.buses["A1"].onboard.remove("r2")
        del sim.riders["r2"]
        r3 = Rider(id="r3", origin_id="X", destination_id="S",
                   arrival_min=0, patience_min=15)
        sim.riders["r3"] = r3
        board(sim, r3, "A1")
        res = execute_handoff(sim, "A1", "B1", "S", ["r3"], 5)
        self.assertFalse(res.ok)
        self.assertIn("not served downstream", res.reason)

    def test_rejects_invalid_ticket(self):
        for tamper in ["missing", "unpaid", "stale_bus", "wrong_dest"]:
            sim = tiny_world()
            rider = sim.riders["r1"]
            if tamper == "missing":
                rider.ticket = None
            elif tamper == "unpaid":
                rider.ticket.fare_paid = False
            elif tamper == "stale_bus":
                rider.ticket.current_bus = "B9"
            else:
                rider.ticket.destination_id = "Z"
            res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 5)
            self.assertFalse(res.ok, tamper)
            self.assertIn("valid ticket", res.reason)
            self.assertEqual(len(sim.ledger), 0)

    def test_rejects_receiver_full(self):
        sim = tiny_world()
        for i in (3, 4):
            r = Rider(id=f"r{i}", origin_id="Z", destination_id="Y",
                      arrival_min=0, patience_min=15)
            sim.riders[r.id] = r
            board(sim, r, "B1")
        res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 5)
        self.assertFalse(res.ok)
        self.assertIn("spare seats", res.reason)
        self.assertEqual(sim.buses["A1"].onboard, ["r1", "r2"])

    def test_receiver_max_load_tracks_transfers(self):
        sim = tiny_world()
        execute_handoff(sim, "A1", "B1", "S", ["r1", "r2"], 5)
        self.assertEqual(sim.buses["B1"].max_load, 2)

    def test_duplicate_rider_ids_deduped(self):
        sim = tiny_world()
        res = execute_handoff(sim, "A1", "B1", "S", ["r1", "r1"], 5)
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(res.moved, ["r1"])
        self.assertEqual(sim.buses["B1"].onboard, ["r1"])


class TestLedger(unittest.TestCase):
    def test_queries(self):
        sim = tiny_world()
        self.assertTrue(execute_handoff(sim, "A1", "B1", "S", ["r1"], 5).ok)
        self.assertTrue(execute_handoff(sim, "B1", "A1", "S", ["r1"], 5).ok)
        self.assertEqual(len(sim.ledger), 2)
        self.assertEqual(len(sim.ledger.transfers_for_rider("r1")), 2)
        self.assertEqual(sim.ledger.transfers_for_rider("r2"), [])
        self.assertEqual(len(sim.ledger.transfers_at_stop("S")), 2)
        self.assertEqual(sim.ledger.transfers_at_stop("X"), [])
        self.assertEqual(len(sim.riders["r1"].ticket.transfer_history), 2)


class TestScriptedPolicy(unittest.TestCase):
    def queue_at(self, sim, stop_id, n, dest="Y"):
        for i in range(n):
            r = Rider(id=f"q{i}", origin_id=stop_id, destination_id=dest,
                      arrival_min=0, patience_min=15)
            sim.riders[r.id] = r
            sim.queues[stop_id].append(r)

    def test_noop_without_shortfall(self):
        sim = tiny_world()  # A1 full, but nobody waiting
        self.assertEqual(scripted_policy(sim, "A1", "S", 5), [])

    def test_noop_with_room_to_spare(self):
        sim = tiny_world(cap_a=4)
        self.queue_at(sim, "S", 1)
        self.assertEqual(scripted_policy(sim, "A1", "S", 5), [])

    def test_moves_shortfall_to_roomiest_bus(self):
        sim = tiny_world()
        self.queue_at(sim, "S", 3)  # shortfall 3, B1 spare 2
        self.assertEqual(scripted_policy(sim, "A1", "S", 5),
                         [("B1", ["r1", "r2"])])

    def test_noop_when_receiver_full(self):
        sim = tiny_world()
        self.queue_at(sim, "S", 3)
        for i in (3, 4):
            r = Rider(id=f"r{i}", origin_id="Z", destination_id="Y",
                      arrival_min=0, patience_min=15)
            sim.riders[r.id] = r
            board(sim, r, "B1")
        self.assertEqual(scripted_policy(sim, "A1", "S", 5), [])

    def test_skips_same_route_bus(self):
        sim = tiny_world()
        self.queue_at(sim, "S", 1)
        a2 = Bus(id="A2", route_id="RA", capacity=2, start_min=0)
        sim.buses["A2"] = a2  # co-located at S at t=5, but same route
        sim._events = sim._timetable()
        self.assertIn("A2", sim.buses_at("S", 5))
        got = scripted_policy(sim, "A1", "S", 5)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], "B1")


class TestHandoffIntegration(unittest.TestCase):
    def run_corridor(self, seed, policy):
        stops, routes, buses = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=seed)
        sim = Simulation(stops, routes, buses, riders, 180,
                         handoff_policy=policy)
        return sim, sim.run()

    def test_scripted_beats_baseline(self):
        _, base = self.run_corridor(42, None)
        sim, res = self.run_corridor(42, scripted_policy)
        self.assertGreater(base.denied_boardings, 0)
        self.assertLess(res.denied_boardings, base.denied_boardings)
        self.assertGreater(res.handoff_events, 0)
        self.assertGreater(res.riders_transferred, 0)
        self.assertEqual(len(sim.ledger), res.riders_transferred)

    def test_scripted_conservation_and_capacity(self):
        sim, res = self.run_corridor(42, scripted_policy)
        self.assertEqual(res.boarded + res.unserved, res.total_riders)
        self.assertEqual(res.alighted + res.onboard_at_end, res.boarded)
        for bus_id, max_load in res.max_load_by_bus.items():
            self.assertLessEqual(max_load, 40, bus_id)
        for t in sim.ledger.transfers:
            rider = sim.riders[t.rider_id]
            self.assertIsNotNone(rider.alight_min, t.rider_id)
        for rider in sim.riders.values():
            hist = rider.ticket.transfer_history if rider.ticket else []
            led = [(t.from_bus, t.to_bus, t.stop_id)
                   for t in sim.ledger.transfers_for_rider(rider.id)]
            self.assertEqual(led, hist, rider.id)
            if hist:
                self.assertEqual(rider.ticket.current_bus, hist[-1][1],
                                 rider.id)

    def test_transferred_tickets_stay_valid(self):
        sim, _ = self.run_corridor(123, scripted_policy)
        self.assertGreater(len(sim.ledger), 0)
        for rider in sim.riders.values():
            if not rider.ticket or not rider.ticket.transfer_history:
                continue
            self.assertTrue(rider.ticket.fare_paid, rider.id)
            self.assertEqual(rider.ticket.destination_id,
                             rider.destination_id, rider.id)
            for frm, to, stop in rider.ticket.transfer_history:
                self.assertIn(frm, sim.buses)
                self.assertIn(to, sim.buses)
                self.assertTrue(sim.stops[stop].shared, stop)

    def test_scripted_deterministic(self):
        _, a = self.run_corridor(7, scripted_policy)
        _, b = self.run_corridor(7, scripted_policy)
        self.assertEqual(a.denied_boardings, b.denied_boardings)
        self.assertEqual(a.handoff_events, b.handoff_events)
        self.assertEqual(a.riders_transferred, b.riders_transferred)
        self.assertEqual(a.boardings_by_route, b.boardings_by_route)

    def test_baseline_runs_no_handoffs(self):
        sim, res = self.run_corridor(42, None)
        self.assertEqual(res.handoff_events, 0)
        self.assertEqual(res.riders_transferred, 0)
        self.assertEqual(len(sim.ledger), 0)


if __name__ == "__main__":
    unittest.main()

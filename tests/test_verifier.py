"""Phase 3 checks: the deterministic verifier approves sound proposals,
rejects every unsafe one with a full diagnosis, and gates the sim loop.
Stdlib unittest only."""
import unittest

from simulator.demand import generate_riders
from simulator.handoff import execute_handoff, reckless_policy, scripted_policy
from simulator.models import Bus, Rider, Route, Stop, Ticket
from simulator.network import build_corridor
from simulator.sim import Simulation
from verifier import ETA_WINDOW_MIN, Proposal, verify


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
    """Two routes (RA: X-S-Y, RB: Z-S-Y) meeting at shared stop S at t=5.

    Riders r1/r2 (X->Y) start onboard A1 with paid tickets.
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


def add_offroute_bus(sim):
    """Bus C1 on route RC (Q-Y), which never serves or dwells at S."""
    sim.stops["Q"] = Stop(id="Q", name="Elsewhere", shared=False)
    sim.routes["RC"] = Route(id="RC", name="C", stop_ids=["Q", "Y"])
    sim.buses["C1"] = Bus(id="C1", route_id="RC", capacity=2, start_min=0)
    sim._events = sim._timetable()
    return sim


def fill_bus(sim, bus_id, first=3):
    for i in range(first, first + sim.buses[bus_id].capacity):
        r = Rider(id=f"r{i}", origin_id="Z", destination_id="Y",
                  arrival_min=0, patience_min=15)
        sim.riders[r.id] = r
        board(sim, r, bus_id)


def propose(from_bus="A1", to_bus="B1", stop="S", riders=("r1",),
            minute=5):
    return Proposal(from_bus=from_bus, to_bus=to_bus, stop_id=stop,
                    rider_ids=tuple(riders), minute=minute)


class TestApprove(unittest.TestCase):
    def test_valid_proposal_approved(self):
        sim = tiny_world()
        verdict = verify(sim, propose())
        self.assertTrue(verdict.approved, verdict.failures)
        self.assertEqual(verdict.failures, [])

    def test_multi_rider_approved(self):
        sim = tiny_world()
        verdict = verify(sim, propose(riders=("r1", "r2")))
        self.assertTrue(verdict.approved, verdict.failures)

    def test_exact_fit_approved(self):
        sim = tiny_world()
        fill_bus(sim, "B1")  # B1 full...
        sim.buses["B1"].onboard.pop()  # ...minus one seat for r1
        verdict = verify(sim, propose())
        self.assertTrue(verdict.approved, verdict.failures)


class TestEntities(unittest.TestCase):
    def test_rejects_unknown_bus_and_stop(self):
        sim = tiny_world()
        for p in [propose(from_bus="ZZ"), propose(to_bus="ZZ"),
                  propose(stop="ZZ")]:
            verdict = verify(sim, p)
            self.assertFalse(verdict.approved, p)
            self.assertTrue(any("unknown" in f for f in verdict.failures))

    def test_rejects_same_bus(self):
        sim = tiny_world()
        verdict = verify(sim, propose(from_bus="A1", to_bus="A1"))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("same bus" in f for f in verdict.failures))

    def test_rejects_non_shared_stop(self):
        sim = tiny_world()
        verdict = verify(sim, propose(stop="X", minute=0))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("not shared" in f for f in verdict.failures))

    def test_rejects_empty_riders(self):
        sim = tiny_world()
        verdict = verify(sim, propose(riders=()))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("no riders" in f for f in verdict.failures))

    def test_rejects_unknown_and_stray_riders(self):
        sim = tiny_world()
        stray = Rider(id="r9", origin_id="X", destination_id="Y",
                      arrival_min=0, patience_min=15)
        sim.riders["r9"] = stray
        for riders, needle in [(("ghost",), "unknown rider"),
                               (("r9",), "not onboard")]:
            verdict = verify(sim, propose(riders=riders))
            self.assertFalse(verdict.approved, riders)
            self.assertTrue(any(needle in f for f in verdict.failures))

    def test_structural_gate_shortcircuits(self):
        sim = tiny_world()
        garbage = Proposal(from_bus="X", to_bus="Y", stop_id="Z",
                           rider_ids=("ghost",), minute=99)
        verdict = verify(sim, garbage)  # must not raise
        self.assertFalse(verdict.approved)
        self.assertGreaterEqual(len(verdict.failures), 3)


class TestDestination(unittest.TestCase):
    def test_rejects_destination_not_downstream(self):
        sim = tiny_world()
        sim.buses["A1"].onboard.remove("r2")
        del sim.riders["r2"]
        r3 = Rider(id="r3", origin_id="X", destination_id="S",
                   arrival_min=0, patience_min=15)
        sim.riders["r3"] = r3
        board(sim, r3, "A1")
        verdict = verify(sim, propose(riders=("r3",)))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("downstream" in f for f in verdict.failures))

    def test_rejects_destination_off_both_routes(self):
        sim = tiny_world()
        sim.riders["r1"].destination_id = "Z"
        sim.riders["r1"].ticket.destination_id = "Z"
        verdict = verify(sim, propose())
        self.assertFalse(verdict.approved)
        self.assertTrue(any("source route" in f for f in verdict.failures))
        self.assertTrue(any("receiver" in f for f in verdict.failures))

    def test_rejects_bus_not_serving_stop(self):
        sim = add_offroute_bus(tiny_world())
        verdict = verify(sim, propose(to_bus="C1"))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("does not serve" in f for f in verdict.failures))


class TestEtaWindow(unittest.TestCase):
    def test_window_boundaries(self):
        sim = tiny_world()  # both dwell at S at t=5
        self.assertEqual(ETA_WINDOW_MIN, 5)
        for minute, approved in [(5, True), (0, True), (10, True),
                                 (11, False), (16, False)]:
            verdict = verify(sim, propose(minute=minute))
            self.assertEqual(verdict.approved, approved, minute)
            if not approved:
                self.assertTrue(
                    any("outside" in f for f in verdict.failures))

    def test_window_checked_per_bus(self):
        sim = tiny_world(b_start=1)  # A1@S t=5, B1@S t=6
        self.assertTrue(verify(sim, propose(minute=5)).approved)
        verdict = verify(sim, propose(minute=0))  # B1 Δ6
        self.assertFalse(verdict.approved)
        self.assertTrue(any("receiver" in f for f in verdict.failures))
        verdict = verify(sim, propose(minute=11))  # A1 Δ6
        self.assertFalse(verdict.approved)
        self.assertTrue(any("source" in f for f in verdict.failures))

    def test_never_dwells_rejected(self):
        sim = add_offroute_bus(tiny_world())
        self.assertEqual(sim.dwells_at("C1", "S"), [])
        verdict = verify(sim, propose(to_bus="C1"))
        self.assertFalse(verdict.approved)
        self.assertTrue(any("never dwells" in f for f in verdict.failures))

    def test_dwells_at_lists_meets(self):
        sim = tiny_world()
        self.assertEqual(sim.dwells_at("A1", "S"), [5])
        self.assertEqual(sim.dwells_at("B1", "S"), [5])
        self.assertEqual(tiny_world(b_start=1).dwells_at("B1", "S"), [6])


class TestCapacity(unittest.TestCase):
    def test_rejects_full_receiver(self):
        sim = tiny_world()
        fill_bus(sim, "B1")
        verdict = verify(sim, propose())
        self.assertFalse(verdict.approved)
        self.assertTrue(any("spare seats" in f for f in verdict.failures))


class TestTickets(unittest.TestCase):
    def test_rejects_invalid_tickets(self):
        cases = {"missing": "has no ticket", "unpaid": "unpaid",
                 "stale_bus": "ticket is on", "wrong_dest": "mismatch"}
        for tamper, needle in cases.items():
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
            verdict = verify(sim, propose())
            self.assertFalse(verdict.approved, tamper)
            self.assertTrue(any(needle in f for f in verdict.failures),
                            verdict.failures)


class TestDiagnosis(unittest.TestCase):
    def test_collects_multiple_failures(self):
        sim = tiny_world()
        fill_bus(sim, "B1")  # capacity fails...
        sim.riders["r1"].destination_id = "Z"  # ...and destination fails
        sim.riders["r1"].ticket.destination_id = "Z"
        verdict = verify(sim, propose())
        self.assertFalse(verdict.approved)
        self.assertGreaterEqual(len(verdict.failures), 2)
        joined = " ".join(verdict.failures)
        self.assertIn("spare seats", joined)
        self.assertIn("downstream", joined)


class TestLayering(unittest.TestCase):
    def test_mechanics_rejects_window_approved(self):
        """Window-timely but inexact proposals pass the verifier yet fail
        at execution: diagnosis vs physical possibility."""
        sim = tiny_world()
        verdict = verify(sim, propose(minute=10))
        self.assertTrue(verdict.approved, verdict.failures)
        res = execute_handoff(sim, "A1", "B1", "S", ["r1"], 10)
        self.assertFalse(res.ok)
        self.assertIn("co-located", res.reason)


class TestIntegration(unittest.TestCase):
    def run_corridor(self, seed, policy):
        stops, routes, buses = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=seed)
        sim = Simulation(stops, routes, buses, riders, 180,
                         handoff_policy=policy)
        return sim, sim.run()

    def test_scripted_all_approved(self):
        for seed, denied in [(42, 0), (7, 5), (123, 0)]:
            _, res = self.run_corridor(seed, scripted_policy)
            self.assertEqual(res.verifier_rejections, 0, seed)
            self.assertEqual(res.denied_boardings, denied, seed)
            self.assertEqual(res.verifier_approvals, res.handoff_events,
                             seed)

    def test_reckless_blocked_but_safe(self):
        sim, res = self.run_corridor(42, reckless_policy)
        self.assertGreater(res.verifier_rejections, 0)
        self.assertEqual(res.boarded + res.unserved, res.total_riders)
        self.assertEqual(res.alighted + res.onboard_at_end, res.boarded)
        for bus_id, max_load in res.max_load_by_bus.items():
            self.assertLessEqual(max_load, 40, bus_id)
        for rider in sim.riders.values():
            hist = rider.ticket.transfer_history if rider.ticket else []
            led = [(t.from_bus, t.to_bus, t.stop_id)
                   for t in sim.ledger.transfers_for_rider(rider.id)]
            self.assertEqual(led, hist, rider.id)
        self.assertLessEqual(res.handoff_events, res.verifier_approvals)

    def test_reckless_deterministic(self):
        _, a = self.run_corridor(7, reckless_policy)
        _, b = self.run_corridor(7, reckless_policy)
        self.assertEqual((a.denied_boardings, a.verifier_approvals,
                          a.verifier_rejections, a.riders_transferred),
                         (b.denied_boardings, b.verifier_approvals,
                          b.verifier_rejections, b.riders_transferred))

    def test_baseline_no_verifier_activity(self):
        _, res = self.run_corridor(42, None)
        self.assertEqual(res.verifier_approvals, 0)
        self.assertEqual(res.verifier_rejections, 0)


if __name__ == "__main__":
    unittest.main()

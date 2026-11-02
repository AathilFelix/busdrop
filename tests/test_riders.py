"""Phase 5 checks: rider consent rules, Spark Open policy wiring, and
sim integration. LLM calls use fakes; no network, no endpoint needed."""
import unittest

from riders import (RiderError, SparkOpenClient, build_messages, build_offer,
                    rider_policy_factory, rule_decision)
from simulator.demand import generate_riders
from simulator.handoff import scripted_policy
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


def tiny_world():
    """A1 (2/2, crush) meets B1 (0/2, empty) at shared stop S, t=5."""
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
        Bus(id="A1", route_id="RA", capacity=2, start_min=0),
        Bus(id="B1", route_id="RB", capacity=2, start_min=0),
    ]
    riders = [
        Rider(id="r1", origin_id="X", destination_id="Y",
              arrival_min=0, patience_min=10),
        Rider(id="r2", origin_id="X", destination_id="Y",
              arrival_min=0, patience_min=25),
    ]
    sim = Simulation(stops, routes, buses, riders, minutes=20)
    for r in riders:
        board(sim, r, "A1")
    return sim


class FakeRiderClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def decide(self, messages):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class TestRule(unittest.TestCase):
    def test_impatient_walks_to_roomier_bus(self):
        self.assertTrue(rule_decision(10, 1.0, 0.0))

    def test_patient_stays_when_gain_is_small(self):
        self.assertFalse(rule_decision(25, 0.6, 0.5))

    def test_patient_flees_crush_for_room(self):
        self.assertTrue(rule_decision(22, 1.0, 0.25))

    def test_seat_lovers_never_walk(self):
        self.assertFalse(rule_decision(24, 1.0, 0.0))
        self.assertFalse(rule_decision(25, 1.0, 0.0))

    def test_never_walks_to_fuller_bus(self):
        self.assertFalse(rule_decision(10, 0.5, 0.75))

    def test_never_walks_to_full_bus(self):
        self.assertFalse(rule_decision(10, 1.0, 0.95))


class TestOffer(unittest.TestCase):
    def test_offer_contents(self):
        sim = tiny_world()
        offer = build_offer(sim, "r1", "A1", "B1", "S", 5)
        self.assertEqual((offer["stop"], offer["minute"]), ("S", 5))
        self.assertEqual(offer["rider"]["patience_min"], 10)
        self.assertEqual(offer["from_bus"]["onboard"], 2)
        self.assertEqual(offer["to_bus"]["onboard"], 0)
        messages = build_messages(offer)
        self.assertEqual([m["role"] for m in messages],
                         ["system", "user"])

    def test_client_init_offline(self):
        client = SparkOpenClient(base_url="http://x", api_key="k")
        self.assertEqual(client.model, "muse-spark-open")


class TestRiderPolicy(unittest.TestCase):
    def test_rule_only_splits_by_patience(self):
        sim = tiny_world()
        policy = rider_policy_factory()
        self.assertTrue(policy(sim, "r1", "A1", "B1", "S", 5))  # eager
        self.assertFalse(policy(sim, "r2", "A1", "B1", "S", 5))  # seat lover

    def test_llm_answer_honored(self):
        sim = tiny_world()
        fake = FakeRiderClient([{"walk": False, "reason": "love my seat"}])
        policy = rider_policy_factory(fake)
        self.assertFalse(policy(sim, "r1", "A1", "B1", "S", 5))
        self.assertEqual(fake.calls, 1)

    def test_llm_error_falls_back_to_rule(self):
        sim = tiny_world()
        fake = FakeRiderClient([RiderError("boom")])
        policy = rider_policy_factory(fake)
        self.assertTrue(policy(sim, "r1", "A1", "B1", "S", 5))
        self.assertEqual(sim.result.rider_errors, 1)


class TestSimIntegration(unittest.TestCase):
    def run_corridor(self, seed, rider_policy):
        stops, routes, buses = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=seed)
        sim = Simulation(stops, routes, buses, riders, 180,
                         handoff_policy=scripted_policy,
                         rider_policy=rider_policy)
        return sim, sim.run()

    def test_all_decline_moves_nobody(self):
        _, res = self.run_corridor(42, lambda *a: False)
        self.assertGreater(res.verifier_approvals, 0)
        self.assertEqual(res.handoff_events, 0)
        self.assertEqual(res.riders_transferred, 0)
        self.assertEqual(res.rider_declines, res.rider_offers)
        self.assertGreater(res.rider_offers, 0)

    def test_all_accept_matches_no_consent(self):
        _, plain = self.run_corridor(42, None)
        _, res = self.run_corridor(42, lambda *a: True)
        self.assertEqual(res.riders_transferred, plain.riders_transferred)
        self.assertEqual(res.handoff_events, plain.handoff_events)
        self.assertEqual(res.rider_declines, 0)

    def test_rule_riders_partially_decline(self):
        sim, res = self.run_corridor(42, rider_policy_factory())
        self.assertGreater(res.rider_offers, 0)
        self.assertGreater(res.rider_declines, 0)
        self.assertLess(res.riders_transferred, res.rider_offers)
        declined_entries = [e for e in sim.dispatcher_log
                            if e["declined_ids"]]
        self.assertTrue(declined_entries)

    def test_policy_crash_counts_as_decline(self):
        def bad_policy(*args):
            raise ValueError("boom")

        _, res = self.run_corridor(42, bad_policy)
        self.assertEqual(res.riders_transferred, 0)
        self.assertEqual(res.rider_errors, res.rider_offers)


if __name__ == "__main__":
    unittest.main()

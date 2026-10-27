"""Phase 4 checks: dispatcher tools, Spark policy wiring, and client
config. LLM calls use fakes; no network, no API key needed.

A live run against muse-spark-1.3-contributor is manual:
MODEL_API_KEY=... python -m simulator.run --dispatcher spark
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from dispatcher import (MODEL_ID, DispatcherError, SparkClient,
                        build_messages, get_corridor_state,
                        spark_policy_factory)
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
    """A1/B1 meet at shared stop S at t=5; r1/r2 (X->Y) onboard A1."""
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
              arrival_min=0, patience_min=15),
        Rider(id="r2", origin_id="X", destination_id="Y",
              arrival_min=0, patience_min=15),
    ]
    sim = Simulation(stops, routes, buses, riders, minutes=20)
    for r in riders:
        board(sim, r, "A1")
    return sim


def queue_at(sim, stop_id, n, dest="Y", first=0):
    for i in range(first, first + n):
        r = Rider(id=f"q{i}", origin_id=stop_id, destination_id=dest,
                  arrival_min=0, patience_min=15)
        sim.riders[r.id] = r
        sim.queues[stop_id].append(r)


class FakeClient:
    """Scripted propose() answers; records calls, makes none."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def propose(self, messages, tool_schema):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeScriptedClient:
    """Answers like scripted_policy by reading the state payload."""

    def __init__(self):
        self.calls = 0

    def propose(self, messages, tool_schema):
        self.calls += 1
        state = json.loads(messages[1]["content"])
        shortfall = state["full_bus"]["shortfall"]
        recv = state["receivers"][0]
        riders = [e["id"] for e in recv["eligible"]]
        return {
            "to_bus": recv["bus"],
            "rider_ids": riders[:min(shortfall, recv["spare_seats"])],
            "explanation": "fake",
        }


class TestModelConfig(unittest.TestCase):
    def test_contributor_model_pinned(self):
        self.assertEqual(MODEL_ID, "muse-spark-1.3-contributor")

    def test_client_init_offline(self):
        client = SparkClient(api_key="test-key")
        self.assertEqual(client.model, MODEL_ID)

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=True):
                from dispatcher.spark import resolve_api_key
                with self.assertRaises(DispatcherError):
                    resolve_api_key(__import__("pathlib").Path(tmp))

    def test_env_key_wins(self):
        from dispatcher.spark import resolve_api_key
        with patch.dict(os.environ, {"MODEL_API_KEY": "env-key",
                                     "META_API_KEY": "meta-key"}):
            self.assertEqual(resolve_api_key(), "env-key")

    def test_meta_key_fallback(self):
        from dispatcher.spark import resolve_api_key
        with patch.dict(os.environ, {"META_API_KEY": "meta-key"}, clear=True):
            self.assertEqual(resolve_api_key(), "meta-key")

    def test_dotenv_key(self):
        from dispatcher.spark import resolve_api_key
        with tempfile.TemporaryDirectory() as tmp:
            root = __import__("pathlib").Path(tmp)
            (root / ".env").write_text(
                "# comment\nMODEL_API_KEY=file-key\n")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(resolve_api_key(root), "file-key")


class TestCorridorState(unittest.TestCase):
    def test_state_contents(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)  # A1 full (2/2): shortfall 3
        state = get_corridor_state(sim, "A1", "S", 5)
        self.assertEqual(state["minute"], 5)
        self.assertEqual(state["stop"], "S")
        full = state["full_bus"]
        self.assertEqual((full["bus"], full["onboard"], full["capacity"],
                          full["waiting"], full["shortfall"]),
                         ("A1", 2, 2, 3, 3))
        self.assertEqual(len(state["receivers"]), 1)
        recv = state["receivers"][0]
        self.assertEqual(recv["bus"], "B1")
        self.assertEqual(recv["spare_seats"], 2)
        self.assertEqual([e["id"] for e in recv["eligible"]], ["r1", "r2"])

    def test_no_receivers_when_co_located_full(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        fill = Rider(id="f1", origin_id="Z", destination_id="Y",
                     arrival_min=0, patience_min=15)
        sim.riders["f1"] = fill
        board(sim, fill, "B1")
        fill2 = Rider(id="f2", origin_id="Z", destination_id="Y",
                      arrival_min=0, patience_min=15)
        sim.riders["f2"] = fill2
        board(sim, fill2, "B1")
        state = get_corridor_state(sim, "A1", "S", 5)
        self.assertEqual(state["receivers"], [])

    def test_messages_carry_state_json(self):
        sim = tiny_world()
        queue_at(sim, "S", 1)
        state = get_corridor_state(sim, "A1", "S", 5)
        messages = build_messages(state)
        self.assertEqual([m["role"] for m in messages],
                         ["system", "user"])
        self.assertTrue(messages[0]["content"])
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["stop"], "S")


class TestSparkPolicy(unittest.TestCase):
    def test_no_call_without_shortfall(self):
        sim = tiny_world()  # nobody waiting
        fake = FakeClient([{"to_bus": "B1", "rider_ids": ["r1"],
                            "explanation": "x"}])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5), [])
        self.assertEqual(fake.calls, 0)

    def test_no_call_without_receivers(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        for i in (1, 2):
            r = Rider(id=f"f{i}", origin_id="Z", destination_id="Y",
                      arrival_min=0, patience_min=15)
            sim.riders[r.id] = r
            board(sim, r, "B1")
        fake = FakeClient([{"to_bus": "B1", "rider_ids": ["r1"],
                            "explanation": "x"}])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5), [])
        self.assertEqual(fake.calls, 0)

    def test_returns_proposal_with_explanation(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        fake = FakeClient([{"to_bus": "B1", "rider_ids": ["r1"],
                            "explanation": "free a seat"}])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5),
                         [("B1", ["r1"], "free a seat")])
        self.assertEqual(fake.calls, 1)

    def test_null_means_skip(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        fake = FakeClient([{"to_bus": None, "rider_ids": [],
                            "explanation": "not worth it"}])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5), [])

    def test_client_error_skips_tick(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        fake = FakeClient([DispatcherError("boom")])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5), [])
        self.assertEqual(sim.result.dispatcher_errors, 1)

    def test_unlisted_receiver_rejected(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        fake = FakeClient([{"to_bus": "ZZ", "rider_ids": ["r1"],
                            "explanation": "hallucinated"}])
        policy = spark_policy_factory(fake)
        self.assertEqual(policy(sim, "A1", "S", 5), [])
        self.assertEqual(sim.result.dispatcher_errors, 1)


class TestSparkIntegration(unittest.TestCase):
    def run_corridor(self, seed, policy):
        stops, routes, buses = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=seed)
        sim = Simulation(stops, routes, buses, riders, 180,
                         handoff_policy=policy)
        return sim, sim.run()

    def test_fake_scripted_matches_scripted(self):
        """The Spark wiring reproduces scripted numbers exactly when the
        (fake) LLM answers like the scripted policy."""
        _, expected = self.run_corridor(42, scripted_policy)
        sim, res = self.run_corridor(
            42, spark_policy_factory(FakeScriptedClient()))
        self.assertEqual(res.denied_boardings, expected.denied_boardings)
        self.assertEqual(res.handoff_events, expected.handoff_events)
        self.assertEqual(res.riders_transferred, expected.riders_transferred)
        self.assertEqual(res.verifier_approvals, expected.verifier_approvals)
        self.assertEqual(res.verifier_rejections,
                         expected.verifier_rejections)
        self.assertEqual(res.dispatcher_errors, 0)
        self.assertEqual(len(sim.dispatcher_log), res.handoff_events)
        for entry in sim.dispatcher_log:
            self.assertTrue(entry["approved"])
            self.assertTrue(entry["explanation"])

    def test_dispatcher_log_records_verdicts(self):
        sim = tiny_world()
        queue_at(sim, "S", 3)
        # B1 spare 2 but fake moves r1 only: valid, approved.
        fake = FakeClient([{"to_bus": "B1", "rider_ids": ["r1"],
                            "explanation": "e1"}])
        sim.handoff_policy = spark_policy_factory(fake)
        sim._process_stop(sim.buses["A1"], "S", 5)
        self.assertEqual(len(sim.dispatcher_log), 1)
        entry = sim.dispatcher_log[0]
        self.assertEqual((entry["minute"], entry["stop_id"],
                          entry["from_bus"], entry["to_bus"],
                          entry["rider_ids"], entry["approved"]),
                         (5, "S", "A1", "B1", ["r1"], True))
        self.assertEqual(entry["explanation"], "e1")


if __name__ == "__main__":
    unittest.main()

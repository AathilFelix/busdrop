"""Phase 7 checks: stop coordinates, bus positions, the run recorder,
and a headless render of the Streamlit app (skipped if Streamlit is
not installed)."""
import json
import unittest
from pathlib import Path
from unittest import skipUnless

from simulator.demand import generate_riders
from simulator.handoff import scripted_policy
from simulator.network import STOP_COORDS, build_corridor, build_stops
from simulator.sim import COOLDOWN_MIN, Simulation

try:
    import streamlit  # noqa: F401
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

REPO = Path(__file__).resolve().parent.parent


def recorded_run(seed=42, policy=None, minutes=180):
    stops, routes, buses = build_corridor()
    riders = generate_riders(stops, routes, minutes, seed=seed)
    sim = Simulation(stops, routes, buses, riders, minutes,
                     handoff_policy=policy, record=True)
    return sim, sim.run()


class TestCoordinates(unittest.TestCase):
    def test_every_stop_has_coords(self):
        for sid in build_stops():
            self.assertIn(sid, STOP_COORDS)
            lat, lon = STOP_COORDS[sid]
            # Chennai bounding box.
            self.assertTrue(13.0 < lat < 13.2, sid)
            self.assertTrue(80.2 < lon < 80.4, sid)

    def test_trunk_runs_south_to_north(self):
        lats = [STOP_COORDS[s][0]
                for s in ["GEM", "THL", "LIC", "SIM", "CEN", "BWY"]]
        self.assertEqual(lats, sorted(lats))


class TestPositions(unittest.TestCase):
    def setUp(self):
        stops, routes, buses = build_corridor()
        self.sim = Simulation(stops, routes, buses, [], 180)

    def test_dwell_minute_pins_to_stop(self):
        # R1-B1: ROY t=0, PYC t=5, THL t=10.
        self.assertEqual(self.sim.bus_position("R1-B1", 0),
                         STOP_COORDS["ROY"])
        self.assertEqual(self.sim.bus_position("R1-B1", 5),
                         STOP_COORDS["PYC"])
        self.assertEqual(self.sim.bus_position("R1-B1", 10),
                         STOP_COORDS["THL"])

    def test_mid_leg_interpolates(self):
        lat, lon = self.sim.bus_position("R1-B1", 2)  # 40% ROY->PYC
        a, b = STOP_COORDS["ROY"], STOP_COORDS["PYC"]
        self.assertAlmostEqual(lat, a[0] + (b[0] - a[0]) * 0.4)
        self.assertAlmostEqual(lon, a[1] + (b[1] - a[1]) * 0.4)

    def test_clamps_before_start_and_after_end(self):
        self.assertEqual(self.sim.bus_position("R1-B2", 0),
                         STOP_COORDS["ROY"])
        self.assertEqual(self.sim.bus_position("R1-B1", 219),
                         STOP_COORDS["BWY"])


class TestRecorder(unittest.TestCase):
    def test_frames_cover_every_minute(self):
        sim, _ = recorded_run()
        self.assertEqual(len(sim.frames), 180 + COOLDOWN_MIN)
        self.assertEqual(sim.frames[0]["minute"], 0)
        frame = sim.frames[100]
        self.assertEqual(set(frame), {"minute", "buses", "queues",
                                     "denied", "handoffs"})
        self.assertEqual(len(frame["buses"]), 30)
        bus = frame["buses"]["R1-B1"]
        self.assertEqual(set(bus), {"route", "lat", "lon", "onboard",
                                   "capacity", "start"})
        # "start" is the bus's scheduled departure minute, consumed by
        # api._slim_frames and the Next.js replay (Diagram started state).
        self.assertIsInstance(bus["start"], int)
        self.assertGreaterEqual(bus["start"], 0)

    def test_denied_is_cumulative(self):
        sim, res = recorded_run()
        denied = [f["denied"] for f in sim.frames]
        self.assertEqual(denied, sorted(denied))
        self.assertEqual(denied[-1], res.denied_boardings)

    def test_scripted_handoffs_captured(self):
        sim, res = recorded_run(policy=scripted_policy)
        events = [h for f in sim.frames for h in f["handoffs"]]
        self.assertEqual(len(events), res.handoff_events)
        self.assertEqual(sum(h["riders"] for h in events),
                         res.riders_transferred)
        self.assertEqual(set(events[0]),
                         {"from_bus", "to_bus", "stop_id", "riders",
                          "explanation"})

    def test_baseline_has_no_handoffs(self):
        sim, _ = recorded_run()
        self.assertTrue(all(f["handoffs"] == [] for f in sim.frames))

    def test_frames_are_json_serializable(self):
        sim, _ = recorded_run(policy=scripted_policy)
        json.dumps(sim.frames)

    def test_recording_off_by_default(self):
        stops, routes, buses = build_corridor()
        riders = generate_riders(stops, routes, 180, seed=42)
        sim = Simulation(stops, routes, buses, riders, 180)
        sim.run()
        self.assertEqual(sim.frames, [])


@skipUnless(HAS_STREAMLIT, "streamlit not installed")
class TestAppRenders(unittest.TestCase):
    def test_app_runs_without_exception(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(REPO / "dashboard" / "app.py"))
        at.run()
        self.assertEqual(at.exception, [])

    def test_product_story_renders(self):
        """The dashboard reads as a product: outcome banner, right-now
        rail, and plain-language metrics — no run A/B jargon."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(REPO / "dashboard" / "app.py"))
        at.run()
        self.assertEqual(at.exception, [])
        texts = ([m.value for m in at.markdown]
                 + [s.value for s in at.success]
                 + [c.value for c in at.caption]
                 + [h.value for h in at.subheader])
        blob = "\n".join(str(t) for t in texts)
        for needle in ("fewer riders left behind", "Right now",
                       "The morning in numbers", "Moves that mattered"):
            self.assertIn(needle, blob)
        labels = [m.label for m in at.metric]
        self.assertIn("Riders left behind", labels)


if __name__ == "__main__":
    unittest.main()

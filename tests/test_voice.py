"""Phase 6 checks: transcript parsing (Tamil/English), voice feed
boosts, dispatcher wiring, and the transcribe client. No network."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dispatcher import get_corridor_state
from simulator.handoff import eligible_waiting
from simulator.models import Bus, Rider, Route, Stop
from simulator.sim import Simulation
from voice import (VoiceClient, VoiceError, VoiceFeed, load_demo, load_file,
                   parse_transcript)


def tiny_world(feed=None):
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
    sim = Simulation(stops, routes, buses, [], minutes=20,
                     voice_feed=feed)
    return sim


class TestParse(unittest.TestCase):
    def test_english_crush(self):
        s = parse_transcript("LIC crush, can't board", 90, "LIC")
        self.assertEqual((s.level, s.language, s.extra_waiting),
                         ("crush", "en", 6))

    def test_english_busy(self):
        s = parse_transcript("crowd building, long queue", 90, "THL")
        self.assertEqual(s.level, "busy")
        self.assertEqual(s.extra_waiting, 3)

    def test_tamil_crush(self):
        s = parse_transcript("Central-la seat illa, yera mudiyala",
                             100, "CEN")
        self.assertEqual((s.level, s.language), ("crush", "ta"))

    def test_tamil_busy(self):
        s = parse_transcript("LIC-la periya koottam", 90, "LIC")
        self.assertEqual((s.level, s.language), ("busy", "ta"))

    def test_all_clear_is_ok(self):
        s = parse_transcript("all clear, moving fine", 90, "LIC")
        self.assertEqual((s.level, s.extra_waiting), ("ok", 0))

    def test_stop_detected_from_text(self):
        s = parse_transcript("Simpson crush, can't board", 90)
        self.assertEqual(s.stop_id, "SIM")

    def test_explicit_stop_wins(self):
        s = parse_transcript("Simpson crush", 90, "LIC")
        self.assertEqual(s.stop_id, "LIC")


class TestFeed(unittest.TestCase):
    def test_boost_within_window_only(self):
        feed = VoiceFeed([parse_transcript("LIC crush", 100, "LIC")])
        self.assertEqual(feed.boost_at("LIC", 105), 6)
        self.assertEqual(feed.boost_at("LIC", 111), 0)  # window is 10
        self.assertEqual(feed.boost_at("LIC", 99), 0)  # no time travel

    def test_wrong_stop_gets_nothing(self):
        feed = VoiceFeed([parse_transcript("LIC crush", 100, "LIC")])
        self.assertEqual(feed.boost_at("CEN", 100), 0)

    def test_stopless_signal_is_not_actionable(self):
        feed = VoiceFeed([parse_transcript("mega crush", 100)])
        self.assertEqual(feed.boost_at("LIC", 100), 0)

    def test_boost_caps(self):
        feed = VoiceFeed([parse_transcript("LIC crush", 100, "LIC")
                          for _ in range(5)])
        self.assertEqual(feed.boost_at("LIC", 100), 12)

    def test_demo_covers_peak_in_two_languages(self):
        feed = load_demo()
        self.assertEqual(len(feed), 4)
        self.assertEqual({s.language for s in feed.signals}, {"ta", "en"})
        self.assertTrue(all(s.stop_id for s in feed.signals))
        self.assertGreater(feed.boost_at("LIC", 95), 0)

    def test_load_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text(json.dumps([
                {"minute": 50, "text": "LIC crush", "stop_id": "LIC"},
                {"minute": 60, "text": "all clear"},
            ]))
            feed = load_file(path)
        self.assertEqual(len(feed), 2)
        self.assertEqual(feed.boost_at("LIC", 50), 6)

    def test_load_file_rejects_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps([{"minute": 1}]))
            with self.assertRaises(ValueError):
                load_file(path)


class TestSimWiring(unittest.TestCase):
    def test_minute_unlocks_boost(self):
        feed = VoiceFeed([parse_transcript("crush", 5, "S")])
        sim = tiny_world(feed)
        self.assertEqual(eligible_waiting(sim, "A1", "S"), 0)
        self.assertEqual(eligible_waiting(sim, "A1", "S", 5), 6)

    def test_no_feed_no_boost(self):
        sim = tiny_world()
        self.assertEqual(eligible_waiting(sim, "A1", "S", 5), 0)

    def test_state_carries_voice_note(self):
        feed = VoiceFeed([parse_transcript("crush", 5, "S")])
        sim = tiny_world(feed)
        state = get_corridor_state(sim, "A1", "S", 5)
        self.assertIn("+6", state["voice"])
        self.assertEqual(state["full_bus"]["waiting"], 6)
        plain = get_corridor_state(tiny_world(), "A1", "S", 5)
        self.assertIsNone(plain["voice"])


class TestTranscribeClient(unittest.TestCase):
    def test_text_passthrough(self):
        self.assertEqual(VoiceClient.transcribe_text("  koottam  "),
                         "koottam")

    def test_missing_audio_errors(self):
        client = VoiceClient(api_key="test-key")
        with self.assertRaises(VoiceError):
            client.transcribe_file("/nonexistent/clip.mp3")

    def test_voice_key_wins(self):
        from voice.transcribe import resolve_api_key
        with patch.dict(os.environ, {"VOICE_API_KEY": "v",
                                     "MODEL_API_KEY": "m"}):
            self.assertEqual(resolve_api_key(), "v")


if __name__ == "__main__":
    unittest.main()

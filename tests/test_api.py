"""API contract: corridor meta and recorded runs for the web frontend."""

from fastapi.testclient import TestClient

from api import app
from dispatcher.spark import DispatcherError, resolve_api_key

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    try:
        resolve_api_key()
        expected_spark = True
    except DispatcherError:
        expected_spark = False
    assert body["spark"] == expected_spark


def test_corridor_shape():
    res = client.get("/api/corridor")
    assert res.status_code == 200
    body = res.json()
    assert body["minutes"] == 180
    assert len(body["stops"]) == 10
    assert len(body["routes"]) == 3
    assert len(body["scenarios"]) == 3
    trunk = [sid for sid, s in body["stops"].items() if s["shared"]]
    assert trunk == ["THL", "LIC", "SIM", "CEN", "BWY"]
    assert body["routes"]["R1"]["stop_ids"][-5:] == trunk


def test_baseline_run_has_frames_and_no_moves():
    res = client.post("/api/run", json={"seed": 42, "dispatcher": "baseline",
                                        "riders": False, "voice": False})
    assert res.status_code == 200
    body = res.json()
    assert len(body["frames"]) == 180 + 40  # + cooldown so buses finish
    assert body["moves"] == []
    assert body["voice"] == []
    assert body["result"]["total"] > 0
    first = body["frames"][0]
    assert first["minute"] == 0
    assert len(first["buses"]) == 30
    assert set(first["queues"]) == set(body["frames"][-1]["queues"])


def test_scripted_run_matches_dashboard_numbers():
    res = client.post("/api/run", json={"seed": 42, "dispatcher": "scripted",
                                        "riders": True, "voice": True})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["moved"] > 0
    assert len(body["voice"]) == 4
    assert body["moves"], "seed 42 scripted must produce moves"
    for move in body["moves"]:
        assert move["riders"] > 0
        assert move["stop_id"] in ("THL", "LIC", "SIM", "CEN", "BWY")


def test_log_entries_carry_destinations():
    res = client.post("/api/run", json={"seed": 42, "dispatcher": "scripted",
                                        "riders": True, "voice": True})
    body = res.json()
    assert body["log"]
    walked = [e for e in body["log"]
              if len(e["rider_ids"]) > len(e["declined_ids"])]
    assert walked
    for e in body["log"]:
        assert isinstance(e["destinations"], list)
    for e in walked:
        assert e["destinations"]
        assert all(isinstance(d, str) for d in e["destinations"])


def test_reckless_run_gets_verifier_rejections():
    res = client.post("/api/run", json={"seed": 42, "dispatcher": "reckless",
                                        "riders": False, "voice": False})
    assert res.status_code == 200
    body = res.json()
    assert body["result"]["rejected"] >= 1
    blocked = [e for e in body["log"] if not e["approved"]]
    assert blocked


def test_spark_without_key_is_502(monkeypatch):
    def no_key(*args, **kwargs):
        raise DispatcherError("No Meta API key")
    monkeypatch.setattr("dispatcher.spark.resolve_api_key", no_key)
    res = client.post("/api/run", json={"seed": 42, "dispatcher": "spark"})
    assert res.status_code == 502
    assert "key" in res.json()["detail"].lower()

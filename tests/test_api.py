import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from sensorscope.config import Settings
from sensorscope.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=tmp_path / "test.sqlite3", simulator=False)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as instance:
        yield instance


def reading(**overrides):
    return {
        "machine_id": "press-01",
        "temperature": 55,
        "vibration": 0.45,
        "current": 12,
        **overrides,
    }


def test_normal_and_anomaly_ingestion_and_filtering(client):
    assert client.post("/api/readings", json=reading()).json()["status"] == "normal"
    response = client.post("/api/readings", json=reading(vibration=0.85, current=15))
    assert response.status_code == 201
    assert response.json()["anomalies"] == ["vibration", "current"]
    events = client.get("/api/events").json()["items"]
    assert len(events) == 1  # One event per reading, even with two unusual metrics.
    assert events[0]["source"] == "external"
    assert events[0]["vibration"] == 0.85
    assert client.get("/api/events?machine_id=motor-02").json()["items"] == []
    history = client.get("/api/readings/press-01").json()["items"]
    assert [r["status"] for r in history] == ["normal", "anomaly"]
    overview = client.get("/api/overview").json()
    assert overview["event_count"] == 1
    assert overview["reading_count"] == 2
    assert overview["machines"][0]["status"] == "anomaly"


@pytest.mark.parametrize(
    "changes",
    [
        {"machine_id": "unknown"},
        {"temperature": 251},
        {"vibration": -1},
        {"current": "nan"},
        {"current": "inf"},
        {"unexpected": 1},
        {"timestamp": "2026-01-01T00:00:00"},
        {"temperature": None},
    ],
)
def test_bad_readings_are_rejected_without_writes(client, changes):
    assert client.post("/api/readings", json=reading(**changes)).status_code == 422
    assert client.get("/api/overview").json()["reading_count"] == 0


def test_future_duplicate_and_older_readings_are_rejected(client):
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert client.post("/api/readings", json=reading(timestamp=future)).status_code == 422
    now = datetime.now(UTC)
    payload = reading(timestamp=now.isoformat())
    assert client.post("/api/readings", json=payload).status_code == 201
    assert client.post("/api/readings", json=payload).status_code == 409
    payload["timestamp"] = (now - timedelta(seconds=1)).isoformat()
    assert client.post("/api/readings", json=payload).status_code == 409
    assert client.get("/api/overview").json()["reading_count"] == 1


def test_timezone_normalization_and_stale_status(client):
    payload = reading(timestamp="2020-01-01T09:00:00+09:00")
    response = client.post("/api/readings", json=payload)
    assert response.status_code == 201
    assert response.json()["timestamp"].startswith("2020-01-01T00:00:00")
    assert client.get("/api/overview").json()["machines"][0]["status"] == "waiting"


def test_data_survives_restart_and_duplicates_still_rejected(settings):
    payload = reading(vibration=0.85)
    with TestClient(create_app(settings)) as first:
        saved = first.post("/api/readings", json=payload).json()
    with TestClient(create_app(settings)) as second:
        assert len(second.get("/api/events").json()["items"]) == 1
        assert second.get("/api/readings/press-01").json()["items"][0]["vibration"] == 0.85
        payload["timestamp"] = saved["timestamp"]
        assert second.post("/api/readings", json=payload).status_code == 409


def test_retention_limits_and_ordering(tmp_path):
    settings = Settings(
        db_path=tmp_path / "retention.sqlite3", simulator=False, reading_limit=3, event_limit=2
    )
    with TestClient(create_app(settings)) as client:
        for i in range(6):
            assert (
                client.post("/api/readings", json=reading(vibration=0.8 + 0.01 * i)).status_code
                == 201
            )
        history = client.get("/api/readings/press-01").json()["items"]
        assert [r["vibration"] for r in history] == pytest.approx([0.83, 0.84, 0.85])
        assert [r["vibration"] for r in client.get("/api/events").json()["items"]] == pytest.approx(
            [0.85, 0.84]
        )


@pytest.mark.parametrize(
    "url",
    [
        "/api/events?limit=0",
        "/api/events?limit=301",
        "/api/readings/unknown",
        "/api/events?machine_id=unknown",
    ],
)
def test_query_validation(client, url):
    assert client.get(url).status_code == 422


def test_dashboard_assets_and_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert "AIFLab SensorScope" in client.get("/").text
    assert client.get("/static/vendor/chart.umd.min.js").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.post("/api/demo/anomaly", json={"machine_id": "press-01"}).status_code == 409


def test_live_simulator_injection_and_external_input_separation(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "live.sqlite3", simulator=True, interval=0.1))
    with TestClient(app) as client:
        assert client.post("/api/readings", json=reading()).status_code == 409
        assert (
            client.post(
                "/api/demo/anomaly", json={"machine_id": "motor-02", "metric": "vibration"}
            ).status_code
            == 202
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            events = client.get("/api/events?machine_id=motor-02").json()["items"]
            if any("vibration" in event["anomalies"] for event in events):
                break
            time.sleep(0.05)
        else:
            pytest.fail("Injected anomaly did not reach SQLite through the live simulator")
        assert client.get("/api/health").status_code == 200
        assert all(event["source"] == "simulator" for event in events)
        app.state.simulator_error = True
        assert client.get("/api/health").status_code == 503
        assert client.post("/api/demo/anomaly", json={"machine_id": "press-01"}).status_code == 503

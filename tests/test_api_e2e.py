from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mission_control_api.main import create_app


@pytest.fixture(autouse=True)
def _clear_mission_env(monkeypatch: pytest.MonkeyPatch):
    for key in [
        "FIREWORKS_API_KEY",
        "GEMMA_ENDPOINT",
        "OPENROUTER_API_KEY",
        "LLM_BACKEND",
        "LIVE_MODE",
        "HF_TOKEN",
        "MISSION_CONTROL_LLM_API_KEY",
        "MISSION_CONTROL_LLM_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("mission_control_api.config.load_dotenv", lambda **kw: None)

    from mission_control_api.usgs_client import USGSEarthquake

    fake_quake = USGSEarthquake(
        usgs_id="test001",
        title="M6.5 Test Earthquake",
        magnitude=6.5,
        place="Test City, Testland",
        latitude=10.0,
        longitude=125.0,
        depth_km=30.0,
        timestamp_ms=1700000000000,
        tsunami=False,
        felt_count=100,
        alert_level="orange",
        significance=650,
    )
    monkeypatch.setattr(
        "mission_control_api.event_engine.fetch_earthquakes",
        lambda feed="significant_month", limit=5: [fake_quake],
    )


def test_mission_control_e2e_streams_demo_sequence():
    app = create_app(test_mode=True)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["service"] == "mission-control-api"
    assert body["live_mode"] == "false"
    assert body["llm_backend"] == "fireworks"

    scenario = client.get("/api/scenario")
    assert scenario.status_code == 200
    assert "M6.5" in scenario.json()["name"]
    assert scenario.json()["agents"] == [
        "Overwatch",
        "Sentinel",
        "Atlas",
        "Pulse",
        "Aegis",
    ]

    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "mission_started"
        assert "M6.5" in first["data"]["scenario"]["name"]

        event = ws.receive_json()
        assert event["type"] == "event"
        assert event["data"]["event_type"] == "earthquake_detected"

        agent_responses = []
        while True:
            message = ws.receive_json()
            if message["type"] == "agent_response":
                agent_responses.append(message)
                continue
            mission_plan = message
            break

        assert len(agent_responses) == 5
        assert {item["data"]["callsign"] for item in agent_responses} == {
            "Overwatch",
            "Sentinel",
            "Atlas",
            "Pulse",
            "Aegis",
        }
        assert mission_plan["type"] == "mission_plan"
        assert mission_plan["data"]["version"] == 1
        assert mission_plan["data"]["overall_risk"] in {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }

        last = mission_plan
        while last["type"] != "mission_complete":
            last = ws.receive_json()

        assert last["type"] == "mission_complete"
        assert last["data"]["plan_version"] >= 20

    status = client.get("/api/status")
    state = client.get("/api/state")
    assert status.status_code == 200
    assert state.status_code == 200
    assert status.json() == state.json()
    payload = state.json()
    assert payload["status"] == "completed"
    assert payload["memory"]["version"] >= 20
    assert payload["memory"]["current_risk"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mission_control_api.llm_client import LLMSettings, load_llm_client_from_env
from mission_control_api.main import create_app
from mission_control_api.prompts import load_prompt


class _FakeOpenAI:
    def __init__(
        self, *, api_key: str, base_url: str | None, timeout: int | None = None
    ):
        self.api_key = api_key
        self.base_url = base_url


@pytest.fixture(autouse=True)
def _clear_mission_env(monkeypatch: pytest.MonkeyPatch):
    for key in [
        "FIREWORKS_API_KEY",
        "GEMMA_ENDPOINT",
        "MISSION_CONTROL_LLM_API_KEY",
        "MISSION_CONTROL_LLM_BASE_URL",
        "MISSION_CONTROL_LLM_MODEL",
        "MISSION_CONTROL_LLM_ENABLED",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
        "LLM_BACKEND",
        "LIVE_MODE",
        "HF_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("mission_control_api.config.load_dotenv", lambda **kw: None)


def test_llm_settings_use_fireworks_env_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
    created = []

    def fake_async_openai(
        *, api_key: str, base_url: str | None, timeout: int | None = None
    ):
        client = _FakeOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        created.append(client)
        return client

    monkeypatch.setattr("openai.AsyncOpenAI", fake_async_openai)

    client = load_llm_client_from_env()

    assert client is not None
    assert client.settings.api_key == "fw-test-key"
    assert client.settings.base_url == "https://api.fireworks.ai/inference/v1"
    assert client.settings.model == "accounts/fireworks/models/gemma-4-26b-a4b-it"
    assert client.active_backend == "Fireworks AI (Gemma)"
    assert created[0].base_url == "https://api.fireworks.ai/inference/v1"
    assert created[0].api_key == "fw-test-key"


def test_llm_settings_use_gemma_endpoint_for_mi300x(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GEMMA_ENDPOINT", "http://mi300x.local/v1")
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-test-key")
    created = []

    def fake_async_openai(
        *, api_key: str, base_url: str | None, timeout: int | None = None
    ):
        client = _FakeOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        created.append(client)
        return client

    monkeypatch.setattr("openai.AsyncOpenAI", fake_async_openai)

    client = load_llm_client_from_env()

    assert client is not None
    assert client.settings.api_key == "EMPTY"
    assert client.settings.base_url == "http://mi300x.local/v1"
    assert client.settings.model == "google/gemma-4-26b-a4b-it"
    assert client.active_backend == "AMD MI300X (vLLM)"
    assert created[0].base_url == "http://mi300x.local/v1"
    assert created[0].api_key == "EMPTY"


def test_prompt_files_match_agent_roles():
    sentinel = load_prompt("sentinel")
    overwatch = load_prompt("overwatch")

    assert "Sentinel" in sentinel
    assert "earthquake response command center" in sentinel.lower()
    assert "Overwatch" in overwatch
    assert "Commander" in overwatch


def test_status_route_alias_matches_state_snapshot():
    app = create_app(test_mode=True)
    client = TestClient(app)

    status = client.get("/api/status")
    state = client.get("/api/state")

    assert status.status_code == 200
    assert state.status_code == 200
    assert status.json() == state.json()


def test_env_example_mentions_required_llm_variables():
    env_file = Path(
        "C:/Users/User/Documents/CIRCLE/mission_control_root/mission-control-api/.env.example"
    )
    content = env_file.read_text(encoding="utf-8")

    assert "FIREWORKS_API_KEY" in content
    assert "GEMMA_ENDPOINT" in content

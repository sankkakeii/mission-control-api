from __future__ import annotations

import os
from unittest.mock import patch

from mission_control_api.config import get_settings
from mission_control_api.llm_client import LLMSettings, load_llm_client_from_env


def test_settings_returns_none_when_no_env():
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("mission_control_api.config.load_dotenv"),
    ):
        settings = get_settings()
        assert settings.fireworks_api_key is None
        assert settings.gemma_endpoint is None
        assert settings.has_live_llm is False


def test_settings_picks_up_fireworks_key():
    env = {
        "FIREWORKS_API_KEY": "fw-test-key-123",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.fireworks_api_key == "fw-test-key-123"
        assert settings.has_live_llm is True


def test_settings_picks_up_gemma_endpoint():
    env = {
        "GEMMA_ENDPOINT": "http://localhost:8000/v1",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.gemma_endpoint == "http://localhost:8000/v1"
        assert settings.has_live_llm is True


def test_settings_gemma_endpoint_takes_priority():
    env = {
        "FIREWORKS_API_KEY": "fw-test-key",
        "GEMMA_ENDPOINT": "http://localhost:8000/v1",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.gemma_endpoint == "http://localhost:8000/v1"
        llm_settings = LLMSettings.from_env()
        assert llm_settings.gemma_endpoint == "http://localhost:8000/v1"
        assert llm_settings.fireworks_api_key == "EMPTY"
        assert "vLLM" in llm_settings.active_backend


def test_settings_fireworks_fallback():
    env = {
        "FIREWORKS_API_KEY": "fw-test-key",
    }
    with patch.dict(os.environ, env, clear=True):
        llm_settings = LLMSettings.from_env()
        assert llm_settings.gemma_endpoint is None
        assert llm_settings.fireworks_api_key == "fw-test-key"
        assert "Fireworks" in llm_settings.active_backend
        assert "gemma" in llm_settings.model


def test_load_llm_client_returns_none_when_no_config():
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("mission_control_api.config.load_dotenv"),
    ):
        client = load_llm_client_from_env()
        assert client is None


def test_load_llm_client_returns_none_when_disabled():
    env = {
        "FIREWORKS_API_KEY": "",
        "GEMMA_ENDPOINT": "",
    }
    with patch.dict(os.environ, env, clear=True):
        client = load_llm_client_from_env()
        assert client is None

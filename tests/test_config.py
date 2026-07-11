from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from mission_control_api.config import get_settings
from mission_control_api.llm_client import LLMSettings, load_llm_client_from_env


@pytest.fixture(autouse=True)
def _no_dotenv():
    with patch("mission_control_api.config.load_dotenv"):
        yield


def test_settings_returns_none_when_no_env():
    with patch.dict(os.environ, {}, clear=True):
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
    with patch.dict(os.environ, {}, clear=True):
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


def test_settings_transformers_backend():
    env = {"LLM_BACKEND": "transformers"}
    with patch.dict(os.environ, env, clear=True):
        settings = get_settings()
        assert settings.llm_backend == "transformers"
        assert settings.has_live_llm is True
        llm_settings = LLMSettings.from_env()
        assert llm_settings.llm_backend == "transformers"
        assert "transformers" in llm_settings.active_backend.lower()
        assert llm_settings.is_configured is True


def test_settings_invalid_backend_raises():
    env = {"LLM_BACKEND": "invalid"}
    with patch.dict(os.environ, env, clear=True):
        try:
            get_settings()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "invalid" in str(e).lower()


def test_load_llm_client_returns_transformers_client():
    env = {"LLM_BACKEND": "transformers"}
    with patch.dict(os.environ, env, clear=True):
        client = load_llm_client_from_env()
        assert client is not None
        assert "Transformers" in type(client).__name__

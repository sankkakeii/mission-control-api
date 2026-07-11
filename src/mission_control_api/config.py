from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_VALID_BACKENDS = {"fireworks", "vllm", "transformers", "openrouter"}


@dataclass(frozen=True)
class MissionControlSettings:
    fireworks_api_key: str | None
    gemma_endpoint: str | None
    openrouter_api_key: str | None
    llm_backend: str
    live_mode: bool

    @property
    def has_live_llm(self) -> bool:
        return bool(
            self.fireworks_api_key
            or self.gemma_endpoint
            or self.openrouter_api_key
            or self.llm_backend == "transformers"
        )


def get_settings() -> MissionControlSettings:
    load_dotenv(override=False)
    fireworks_api_key = (
        os.getenv("FIREWORKS_API_KEY")
        or os.getenv("MISSION_CONTROL_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    gemma_endpoint = (
        os.getenv("GEMMA_ENDPOINT")
        or os.getenv("MISSION_CONTROL_LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
    )
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    raw_backend = os.getenv("LLM_BACKEND", "").strip().lower()
    if raw_backend and raw_backend not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid LLM_BACKEND={raw_backend!r}. Must be one of: {', '.join(sorted(_VALID_BACKENDS))}"
        )
    if raw_backend:
        llm_backend = raw_backend
    elif gemma_endpoint:
        llm_backend = "vllm"
    elif openrouter_api_key:
        llm_backend = "openrouter"
    elif fireworks_api_key:
        llm_backend = "fireworks"
    else:
        llm_backend = "fireworks"
    live_mode = os.getenv("LIVE_MODE", "").strip() in ("1", "true", "yes")
    return MissionControlSettings(
        fireworks_api_key=fireworks_api_key,
        gemma_endpoint=gemma_endpoint,
        openrouter_api_key=openrouter_api_key,
        llm_backend=llm_backend,
        live_mode=live_mode,
    )

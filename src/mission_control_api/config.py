from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class MissionControlSettings:
    fireworks_api_key: str | None
    gemma_endpoint: str | None

    @property
    def has_live_llm(self) -> bool:
        return bool(self.fireworks_api_key or self.gemma_endpoint)


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
    return MissionControlSettings(
        fireworks_api_key=fireworks_api_key,
        gemma_endpoint=gemma_endpoint,
    )

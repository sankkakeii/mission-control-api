from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .config import get_settings


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_FIREWORKS_MODEL = "accounts/fireworks/models/gemma-4-26b-a4b-it"
_GEMMA_MODEL = "google/gemma-4-26b-a4b-it"
_FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"


class MissionLLMClient(Protocol):
    async def complete_json(
        self,
        *,
        schema_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class LLMSettings:
    fireworks_api_key: str | None
    gemma_endpoint: str | None
    model: str

    @classmethod
    def from_env(cls) -> "LLMSettings":
        settings = get_settings()
        if settings.gemma_endpoint:
            return cls(
                fireworks_api_key="EMPTY",
                gemma_endpoint=settings.gemma_endpoint,
                model=_GEMMA_MODEL,
            )
        if settings.fireworks_api_key:
            return cls(
                fireworks_api_key=settings.fireworks_api_key,
                gemma_endpoint=None,
                model=_FIREWORKS_MODEL,
            )
        return cls(fireworks_api_key=None, gemma_endpoint=None, model=_FIREWORKS_MODEL)

    @property
    def active_backend(self) -> str:
        return "AMD MI300X (vLLM)" if self.gemma_endpoint else "Fireworks AI (Gemma)"

    @property
    def base_url(self) -> str | None:
        return self.gemma_endpoint or _FIREWORKS_BASE_URL

    @property
    def api_key(self) -> str | None:
        return self.fireworks_api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.fireworks_api_key or self.gemma_endpoint)


class OpenAICompatibleLLMClient:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings.from_env()
        if not self.settings.is_configured:
            raise ValueError("No live LLM backend is configured")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self.settings.api_key, base_url=self.settings.base_url)

    @property
    def active_backend(self) -> str:
        return self.settings.active_backend

    async def complete_json(
        self,
        *,
        schema_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self.settings.model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned non-object JSON for {schema_name}")
        return parsed


def load_llm_client_from_env() -> MissionLLMClient | None:
    settings = LLMSettings.from_env()
    if not settings.is_configured:
        return None
    return OpenAICompatibleLLMClient(settings)


def _parse_json_content(text: str) -> Any:
    raw = text.strip()
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)

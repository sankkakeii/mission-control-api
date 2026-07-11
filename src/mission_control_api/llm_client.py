from __future__ import annotations

import asyncio
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
_OPENROUTER_MODEL = "google/gemma-4-26b-it"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_TIMEOUT_SECONDS = 30


class MissionLLMClient(Protocol):
    async def complete_json(
        self,
        *,
        schema_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LLMSettings:
    fireworks_api_key: str | None
    gemma_endpoint: str | None
    openrouter_api_key: str | None
    llm_backend: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMSettings":
        settings = get_settings()
        if settings.llm_backend == "transformers":
            return cls(
                fireworks_api_key=None,
                gemma_endpoint=None,
                openrouter_api_key=None,
                llm_backend="transformers",
                model=_GEMMA_MODEL,
            )
        if settings.gemma_endpoint:
            return cls(
                fireworks_api_key="EMPTY",
                gemma_endpoint=settings.gemma_endpoint,
                openrouter_api_key=None,
                llm_backend="vllm",
                model=_GEMMA_MODEL,
            )
        if settings.openrouter_api_key:
            return cls(
                fireworks_api_key=None,
                gemma_endpoint=None,
                openrouter_api_key=settings.openrouter_api_key,
                llm_backend="openrouter",
                model=_OPENROUTER_MODEL,
            )
        if settings.fireworks_api_key:
            return cls(
                fireworks_api_key=settings.fireworks_api_key,
                gemma_endpoint=None,
                openrouter_api_key=None,
                llm_backend="fireworks",
                model=_FIREWORKS_MODEL,
            )
        return cls(
            fireworks_api_key=None,
            gemma_endpoint=None,
            openrouter_api_key=None,
            llm_backend="fireworks",
            model=_FIREWORKS_MODEL,
        )

    @property
    def active_backend(self) -> str:
        if self.llm_backend == "transformers":
            return "AMD MI300X (transformers/Gemma)"
        if self.gemma_endpoint:
            return "AMD MI300X (vLLM)"
        if self.llm_backend == "openrouter":
            return "OpenRouter (Gemma)"
        return "Fireworks AI (Gemma)"

    @property
    def base_url(self) -> str | None:
        if self.gemma_endpoint:
            return self.gemma_endpoint
        if self.openrouter_api_key:
            return _OPENROUTER_BASE_URL
        return _FIREWORKS_BASE_URL

    @property
    def api_key(self) -> str | None:
        if self.openrouter_api_key:
            return self.openrouter_api_key
        return self.fireworks_api_key

    @property
    def is_configured(self) -> bool:
        return bool(
            self.fireworks_api_key
            or self.gemma_endpoint
            or self.llm_backend == "transformers"
        )


class OpenAICompatibleLLMClient:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings.from_env()
        if not self.settings.is_configured:
            raise ValueError("No live LLM backend is configured")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            timeout=LLM_TIMEOUT_SECONDS,
        )

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
        response = await asyncio.wait_for(
            self._client.chat.completions.create(
                model=self.settings.model,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            ),
            timeout=LLM_TIMEOUT_SECONDS + 5,
        )
        content = response.choices[0].message.content or "{}"
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned non-object JSON for {schema_name}")
        return parsed


class TransformersLLMClient:
    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings.from_env()
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._patch_grouped_mm_if_needed(torch)

        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
        print(
            f"[TransformersLLMClient] Loading {self.settings.model} (this takes a minute)..."
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.settings.model, token=hf_token or True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.settings.model,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            token=hf_token or True,
        )
        device = getattr(self._model, "hf_device_map", "cpu")
        print(f"[TransformersLLMClient] Model loaded. device_map={device}")

    @staticmethod
    def _patch_grouped_mm_if_needed(torch_module: Any) -> None:
        if not hasattr(torch_module, "_grouped_mm"):
            return
        original = torch_module._grouped_mm
        try:
            result = original(torch.randn(2, 4), torch.randn(2, 4))
            if result is not None:
                return
        except Exception:
            pass

        def _fallback_grouped_mm(a: Any, b: Any, **kwargs: Any) -> Any:
            if a.dim() == 2 and b.dim() == 2:
                return a @ b
            if a.dim() == 3 and b.dim() == 3:
                return torch_module.stack([a[i] @ b[i] for i in range(a.shape[0])])
            return a @ b

        torch_module._grouped_mm = _fallback_grouped_mm
        print(
            "[TransformersLLMClient] Patched torch._grouped_mm with loop fallback for ROCm compatibility"
        )

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
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            None,
            self._generate_json,
            system_prompt,
            user_prompt,
        )
        parsed = _parse_json_content(content)
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned non-object JSON for {schema_name}")
        return parsed

    def _generate_json(self, system_prompt: str, user_prompt: str) -> str:
        import torch

        self._ensure_loaded()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        input_text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(input_text, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(generated, skip_special_tokens=True)


def load_llm_client_from_env() -> MissionLLMClient | None:
    settings = LLMSettings.from_env()
    if not settings.is_configured:
        return None
    if settings.llm_backend == "transformers":
        return TransformersLLMClient(settings)
    return OpenAICompatibleLLMClient(settings)


def _parse_json_content(text: str) -> Any:
    raw = text.strip()
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)

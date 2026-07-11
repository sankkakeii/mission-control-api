from __future__ import annotations

from importlib import resources


_PROMPT_PACKAGE = __package__


def load_prompt(agent_key: str) -> str:
    resource = resources.files(_PROMPT_PACKAGE).joinpath(f"{agent_key}.txt")
    return resource.read_text(encoding="utf-8").strip()

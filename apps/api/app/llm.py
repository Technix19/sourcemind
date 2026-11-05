"""Server-side LLM adapter. The only module that knows about a model provider (Anthropic's Claude).

Generation is off unless BOTH ANTHROPIC_API_KEY and ANTHROPIC_MODEL are set.
The key is read from the environment by the SDK at call time and is never
stored on an object, logged, or returned to a client.
"""
from __future__ import annotations

import os
from typing import Protocol

from .config import get_settings


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str: ...


class GenerationRefused(Exception):
    """The model declined this request (stop_reason "refusal"). The caller shows evidence instead."""


class ClaudeClient:
    def __init__(self, model: str, max_tokens: int, effort: str = "low") -> None:
        self.model = model
        self._max_tokens = max_tokens  # covers the answer AND any thinking the model does
        self._effort = effort

    def complete(self, system: str, user: str) -> str:
        import anthropic  # imported lazily: not needed in sources-only mode

        extra = {"output_config": {"effort": self._effort}} if self._effort else {}
        response = anthropic.Anthropic(timeout=45.0, max_retries=1).messages.create(
            model=self.model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **extra,
        )
        if response.stop_reason == "refusal":
            raise GenerationRefused()
        # Only the visible text: thinking blocks are never shown or used as the answer.
        return "".join(b.text for b in response.content if b.type == "text").strip()


def generation_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY")) and bool(get_settings().chat_model)


def get_llm_client() -> LLMClient | None:
    if not generation_available():
        return None
    settings = get_settings()
    return ClaudeClient(settings.chat_model, settings.max_answer_tokens, settings.answer_effort)

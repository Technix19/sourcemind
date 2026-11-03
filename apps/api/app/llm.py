"""Server-side LLM adapter. The only module that knows about a model provider.

Generation is off unless BOTH OPENAI_API_KEY and OPENAI_CHAT_MODEL are set.
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


class OpenAIClient:
    def __init__(self, model: str, max_output_tokens: int) -> None:
        self.model = model
        self._max_output_tokens = max_output_tokens

    def complete(self, system: str, user: str) -> str:
        from openai import OpenAI  # imported lazily: not needed in sources-only mode

        response = OpenAI(timeout=25.0, max_retries=1).responses.create(
            model=self.model,
            store=False,  # ask the provider not to retain the request
            instructions=system,
            input=user,
            max_output_tokens=self._max_output_tokens,
        )
        return (response.output_text or "").strip()


def generation_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and bool(get_settings().chat_model)


def get_llm_client() -> LLMClient | None:
    if not generation_available():
        return None
    settings = get_settings()
    return OpenAIClient(settings.chat_model, settings.max_answer_tokens)

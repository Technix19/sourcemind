import sys
import types

import pytest

from app.config import get_settings
from app.llm import ClaudeClient, GenerationRefused, get_llm_client


def test_factory_returns_none_without_key_or_model(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_MODEL", "m")
    assert get_llm_client() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_MODEL", "")
    assert get_llm_client() is None


def test_factory_builds_client_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_MODEL", "my-model")
    client = get_llm_client()
    assert client.model == "my-model"
    assert "k" not in vars(client).values()  # the key is never stored on the client


def fake_anthropic(monkeypatch, response):
    seen = {}

    class FakeMessages:
        def create(self, **kwargs):
            seen.update(kwargs)
            return response

    class FakeAnthropic:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs
            self.messages = FakeMessages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=FakeAnthropic))
    return seen


def block(kind, text=""):
    return types.SimpleNamespace(type=kind, text=text)


def reply(*blocks, stop="end_turn"):
    return types.SimpleNamespace(content=list(blocks), stop_reason=stop)


def test_claude_client_sends_a_bounded_request_with_the_prompt_in_the_system_channel(monkeypatch):
    seen = fake_anthropic(monkeypatch, reply(block("text", "  answer [1]  ")))
    out = ClaudeClient("m", 123, "low").complete("SYSTEM", "USER")
    assert out == "answer [1]"
    assert seen["model"] == "m" and seen["system"] == "SYSTEM" and seen["max_tokens"] == 123
    assert seen["messages"] == [{"role": "user", "content": "USER"}]
    assert seen["output_config"] == {"effort": "low"}
    assert "thinking" not in seen and "temperature" not in seen   # rejected by current models
    assert seen["client_kwargs"]["timeout"] > 0 and "api_key" not in seen["client_kwargs"]


def test_only_visible_text_is_returned_never_thinking(monkeypatch):
    fake_anthropic(monkeypatch, reply(block("thinking", "SECRET REASONING"), block("text", "The answer [1].")))
    assert ClaudeClient("m", 100).complete("s", "u") == "The answer [1]."


def test_an_empty_effort_is_left_out_for_models_that_do_not_support_it(monkeypatch):
    seen = fake_anthropic(monkeypatch, reply(block("text", "x")))
    ClaudeClient("m", 100, "").complete("s", "u")
    assert "output_config" not in seen


def test_a_refusal_raises_so_the_caller_falls_back_to_evidence(monkeypatch):
    fake_anthropic(monkeypatch, reply(stop="refusal"))
    with pytest.raises(GenerationRefused):
        ClaudeClient("m", 100).complete("s", "u")


def test_a_response_cut_off_before_any_text_is_empty_not_an_error(monkeypatch):
    fake_anthropic(monkeypatch, reply(block("thinking", "..."), stop="max_tokens"))
    assert ClaudeClient("m", 100).complete("s", "u") == ""


def test_settings_defaults_and_effort_validation(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_EFFORT", raising=False)
    monkeypatch.delenv("MAX_ANSWER_TOKENS", raising=False)
    assert get_settings().answer_effort == "low" and get_settings().max_answer_tokens == 2000
    monkeypatch.setenv("ANTHROPIC_EFFORT", "HIGH")
    assert get_settings().answer_effort == "high"
    monkeypatch.setenv("ANTHROPIC_EFFORT", "nonsense")
    assert get_settings().answer_effort == "low"
    monkeypatch.setenv("ANTHROPIC_EFFORT", "")
    assert get_settings().answer_effort == ""


def test_token_usage_of_the_last_call_is_exposed_for_cost_tracking(monkeypatch):
    response = reply(block("text", "ok"))
    response.usage = types.SimpleNamespace(input_tokens=11, output_tokens=7)
    fake_anthropic(monkeypatch, response)
    client = ClaudeClient("m", 100)
    assert client.last_usage is None
    client.complete("s", "u")
    assert client.last_usage == {"input_tokens": 11, "output_tokens": 7}

import sys
import types

from app.llm import OpenAIClient, get_llm_client


def test_factory_returns_none_without_key_or_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "m")
    assert get_llm_client() is None
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "")
    assert get_llm_client() is None


def test_factory_builds_client_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "my-model")
    client = get_llm_client()
    assert client.model == "my-model"
    assert "k" not in vars(client).values()  # the key is never stored on the client


def test_openai_client_sends_a_bounded_non_retained_request(monkeypatch):
    seen = {}

    class FakeResponses:
        def create(self, **kwargs):
            seen.update(kwargs)
            return types.SimpleNamespace(output_text="  answer [1]  ")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    out = OpenAIClient("m", 123).complete("SYSTEM", "USER")
    assert out == "answer [1]"
    assert seen["model"] == "m" and seen["instructions"] == "SYSTEM" and seen["input"] == "USER"
    assert seen["store"] is False and seen["max_output_tokens"] == 123
    assert seen["client_kwargs"]["timeout"] > 0 and "api_key" not in seen["client_kwargs"]

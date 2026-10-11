from types import SimpleNamespace

import anthropic
import httpx2
import pytest


def test_literal_uses_first_label_alternative_and_sentence_case():
    from medbridge.translate import literal

    assert literal(["me / I", "stomach", "hurt"]) == ("Me stomach hurt.", "precise-literal")


class FakeMessages:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


class FakeClient:
    def __init__(self, **kw):
        self.messages = FakeMessages(**kw)

    def with_options(self, **kw):
        return self


def test_llm_rephrases_glosses():
    from medbridge.translate import LlmTranslator

    client = FakeClient(reply="My stomach hurts.\n")
    t = LlmTranslator(client=client, model="claude-haiku-4-5")
    assert t(["stomach", "hurt"]) == ("My stomach hurts.", "precise-llm")
    call = client.messages.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert "stomach hurt" in call["messages"][0]["content"].lower()


def test_llm_failure_falls_back_to_literal():
    from medbridge.translate import LlmTranslator

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    t = LlmTranslator(client=FakeClient(error=anthropic.APIConnectionError(request=req)), model="m")
    assert t(["stomach", "hurt"]) == ("Stomach hurt.", "precise-literal")


def test_make_translator_reads_env(monkeypatch):
    from medbridge.translate import LlmTranslator, literal, make_translator

    monkeypatch.setenv("GLOSS_TRANSLATOR", "literal")
    assert make_translator() is literal
    monkeypatch.setenv("GLOSS_TRANSLATOR", "llm")
    assert isinstance(make_translator(client=FakeClient(reply="x")), LlmTranslator)

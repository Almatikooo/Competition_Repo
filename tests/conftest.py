"""Tests never reach the real GPU or write to the answer cache, whatever the developer's .env says.
Tests that need a model point the client at a fake vLLM server themselves (see test_guardrails.fake_llm)."""
import pytest

from app.llm.client import llm


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch):
    monkeypatch.setattr(llm, "base_url", "")
    monkeypatch.setattr(llm, "cache_enabled", False)
    monkeypatch.setattr(llm, "_status", {})

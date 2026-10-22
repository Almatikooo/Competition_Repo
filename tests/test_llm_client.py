"""The model client spends GPU time only when it must: kept answers, a fast fallback while the GPU is off,
and a limit on parallel requests. A fake vLLM server stands in for the GPU."""
import asyncio
import json

import httpx
import pytest

from app.llm.client import LLMClient, LLMUnavailable

ASK = [{"role": "user", "content": "Say hi"}]


def fake_vllm(answers: list[str] | None = None, online: bool = True, delay: float = 0.0):
    log = {"chat": 0, "running": 0, "peak": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200 if online else 502, json={"data": [{"id": "fake-qwen"}]})
        log["chat"] += 1
        log["running"] += 1
        log["peak"] = max(log["peak"], log["running"])
        await asyncio.sleep(delay)
        log["running"] -= 1
        text = (answers or ["hi"])[min(log["chat"], len(answers or ["hi"])) - 1]
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    return httpx.MockTransport(handler), log


def client(tmp_path, transport, **kw) -> LLMClient:
    c = LLMClient(transport=transport, cache_dir=tmp_path / "llm", saved=tmp_path / "saved.jsonl", **kw)
    c.base_url = "http://fake-vllm/v1"
    return c


def test_a_kept_answer_needs_no_gpu_even_after_a_restart(tmp_path):
    transport, log = fake_vllm(["hello"])
    assert asyncio.run(client(tmp_path, transport).chat(ASK)) == "hello"
    offline, offline_log = fake_vllm(online=False)
    again = client(tmp_path, offline)                    # a fresh process, GPU switched off
    assert asyncio.run(again.chat(ASK)) == "hello"
    assert log["chat"] == 1 and offline_log["chat"] == 0
    with pytest.raises(LLMUnavailable, match="offline"):  # a new question cannot be answered while it is off...
        asyncio.run(again.chat([{"role": "user", "content": "Something new"}]))
    assert offline_log["chat"] == 0                      # ...and fails at once, without a chat request


def test_answers_a_guardrail_rejects_are_not_kept(tmp_path):
    transport, log = fake_vllm(["invented 42%", "grounded"])
    c = client(tmp_path, transport)
    assert asyncio.run(c.chat(ASK, accept=lambda raw: "%" not in raw)) == "invented 42%"
    assert asyncio.run(c.chat(ASK, accept=lambda raw: "%" not in raw)) == "grounded"     # asked again, not replayed
    assert asyncio.run(c.chat(ASK, accept=lambda raw: "%" not in raw)) == "grounded"     # now kept
    assert log["chat"] == 2


def test_saved_answers_for_the_demo_are_used(tmp_path):
    offline, log = fake_vllm(online=False)
    c = client(tmp_path, offline)
    key = c._key(c.payload(ASK))
    (tmp_path / "saved.jsonl").write_text(json.dumps({"k": key, "v": "saved hello"}) + "\n")
    assert asyncio.run(c.chat(ASK)) == "saved hello" and log["chat"] == 0


def test_at_most_max_parallel_requests_reach_the_gpu(tmp_path):
    transport, log = fake_vllm(delay=0.05)
    c = client(tmp_path, transport, max_parallel=2)

    async def many():
        await asyncio.gather(*(c.chat([{"role": "user", "content": f"q{i}"}], cache=False) for i in range(6)))

    asyncio.run(many())
    assert log["chat"] == 6 and log["peak"] == 2

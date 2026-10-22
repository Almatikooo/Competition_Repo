"""Minimal client for any OpenAI-compatible chat endpoint.

Works with vLLM on a RunPod pod  (LLM_BASE_URL=https://<POD_ID>-8000.proxy.runpod.net/v1; `python -m scripts.gpu create`),
RunPod Serverless vLLM            (LLM_BASE_URL=https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1),
or a local Ollama / LM Studio server. When nothing is configured the app runs in rule-based mode.

The GPU is switched on only when needed, so the client
* answers a request it has seen before from its answer cache, without the GPU (data/cache/llm, plus the committed
  saved answers in data/ai/answers.jsonl);
* fails fast while the model is offline, so callers fall back to the rule-based path at once;
* sends at most `max_parallel` requests at a time to the single GPU.
"""
import asyncio
import datetime as dt
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from .. import config


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, max_parallel: int | None = None,
                 cache_dir: Path | None = config.LLM_CACHE_DIR, saved: Path | None = config.LLM_SAVED_ANSWERS) -> None:
        self.base_url = config.LLM_BASE_URL
        self.model = config.LLM_MODEL
        self.transport = transport  # tests inject httpx.MockTransport here
        self.max_parallel = max_parallel or config.LLM_MAX_PARALLEL
        self.timeout = config.LLM_TIMEOUT
        self.cache_enabled = cache_dir is not None
        self.cache_file = cache_dir / "answers.jsonl" if cache_dir else None
        self.saved_file = saved
        self._answers: dict[str, str] | None = None
        self._status: dict = {}
        self._checked_at = 0.0
        self._sem: tuple[asyncio.AbstractEventLoop, asyncio.Semaphore] | None = None

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self.transport)

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem[0] is not loop:
            self._sem = (loop, asyncio.Semaphore(self.max_parallel))
        return self._sem[1]

    # ------------------------------------------------------------ answer cache
    def _key(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _load_answers(self) -> dict[str, str]:
        if self._answers is None:
            self._answers = {}
            for path in (self.saved_file, self.cache_file):
                if path and path.exists():
                    for line in path.read_text(encoding="utf-8").splitlines():
                        try:
                            row = json.loads(line)
                            self._answers[row["k"]] = row["v"]
                        except (ValueError, KeyError):
                            continue
        return self._answers

    def cached(self, payload: dict) -> str | None:
        return self._load_answers().get(self._key(payload)) if self.cache_enabled else None

    def _remember(self, payload: dict, content: str) -> None:
        if not (self.cache_enabled and self.cache_file and content):
            return
        key = self._key(payload)
        self._load_answers()[key] = content
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        row = {"k": key, "v": content, "model": payload.get("model"), "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        with self.cache_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------ status and chat
    async def status(self, max_age: float = 30.0) -> dict:
        if not self.configured:
            return {"online": False, "configured": False, "model": None, "mode": "rules"}
        if time.time() - self._checked_at < max_age and self._status:
            return self._status
        try:
            async with self._client(8) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                resp.raise_for_status()
                served = [m.get("id") for m in resp.json().get("data", [])]
            self._status = {"online": True, "configured": True, "model": self.model, "served": served, "mode": "llm"}
        except Exception as exc:
            self._status = {"online": False, "configured": True, "model": self.model, "mode": "rules",
                            "error": f"{type(exc).__name__}: {exc}"[:200]}
        self._checked_at = time.time()
        return self._status

    def payload(self, messages: list[dict], *, json_schema: dict | None = None, max_tokens: int = 700,
                temperature: float = 0.2) -> dict:
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if config.LLM_DISABLE_THINKING:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if json_schema:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "output", "schema": json_schema, "strict": True}}
        return payload

    async def chat(self, messages: list[dict], *, json_schema: dict | None = None, max_tokens: int = 700,
                   temperature: float = 0.2, cache: bool = True, accept: Callable[[str], bool] | None = None) -> str:
        """The model's answer. With `cache`, a request seen before is answered from the cache, and a new answer is
        kept when `accept` (e.g. a guardrail) passes it: a rejected answer is never replayed, the next try asks again."""
        if not self.configured:
            raise LLMUnavailable("LLM_BASE_URL is not set")
        payload = self.payload(messages, json_schema=json_schema, max_tokens=max_tokens, temperature=temperature)
        if cache and (hit := self.cached(payload)) is not None:
            return hit
        if not (await self.status()).get("online"):
            raise LLMUnavailable(f"the model is offline ({self._status.get('error', 'no answer')})")
        try:
            async with self._semaphore():
                async with self._client(self.timeout) as client:
                    resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            self._status = {}
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if cache and _passes(accept, content):
            self._remember(payload, content)
        return content


def _passes(accept: Callable[[str], bool] | None, content: str) -> bool:
    if accept is None:
        return True
    try:
        return bool(accept(content))
    except Exception:
        return False


llm = LLMClient()

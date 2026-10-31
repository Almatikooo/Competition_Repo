"""Minimal client for any OpenAI-compatible chat endpoint.

Works with vLLM on a RunPod pod  (LLM_BASE_URL=https://<POD_ID>-8000.proxy.runpod.net/v1; `python -m scripts.gpu create`),
RunPod Serverless vLLM            (LLM_BASE_URL=https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1),
or a local Ollama / LM Studio server. When nothing is configured the app runs in rule-based mode.

The GPU is switched on only when needed, so the client
* answers a request it has seen before from its answer cache, without the GPU (data/cache/llm, plus the committed
  saved answers in data/ai/answers.jsonl). The web app's client (`live_first=True`) does this only while our GPU is
  off: when it is on, every answer is written live, so a demo shows the model at work; the saved answers (the six
  example people's script) stand in when it is off, or when a live draft fails its fact check;
* fails fast while the model is offline, so callers fall back to the rule-based path at once;
* sends at most `max_parallel` requests at a time to the single GPU;
* while the GPU is off, the web app's client (`backup=True`) asks a hosted copy of the same open model instead
  (LLM_BACKUP_*: Groq's qwen/qwen3.8-27b). Callers opt out per request (`backup=False`, e.g. reading a CV, which
  may hold a name or a phone number), and batch scripts make their own client without the backup.
"""
import asyncio
import contextvars
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


# The model that wrote the answer to the current request (our GPU's or the backup's), for the reply's "model" field.
ANSWERED_BY: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_answered_by", default=None)
# How the current request was answered: "gpu" (our model, live), "backup" (the hosted copy, live) or "saved" (an
# answer kept from before, e.g. the example people's script while our GPU is off), for the reply's "source" field.
ANSWER_SOURCE: contextvars.ContextVar[str | None] = contextvars.ContextVar("llm_answer_source", default=None)


class LLMClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, max_parallel: int | None = None,
                 cache_dir: Path | None = config.LLM_CACHE_DIR, saved: Path | None = config.LLM_SAVED_ANSWERS,
                 backup: bool = False, live_first: bool = False) -> None:
        self.base_url = config.LLM_BASE_URL
        self.model = config.LLM_MODEL
        self.backup_url = config.LLM_BACKUP_BASE_URL if backup else ""
        self.backup_model = config.LLM_BACKUP_MODEL
        self.live_first = live_first
        self.transport = transport  # tests inject httpx.MockTransport here
        self.max_parallel = max_parallel or config.LLM_MAX_PARALLEL
        self.timeout = config.LLM_TIMEOUT
        self.cache_enabled = cache_dir is not None
        self.cache_file = cache_dir / "answers.jsonl" if cache_dir else None
        self.saved_file = saved
        self._answers: dict[str, str] | None = None
        self._status: dict = {}
        self._checked_at = 0.0
        self._sems: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Semaphore]] = {}

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self.transport)

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    @property
    def backup_configured(self) -> bool:
        return bool(self.backup_url and config.LLM_BACKUP_API_KEY)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}

    def _semaphore(self, which: str = "gpu") -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if which not in self._sems or self._sems[which][0] is not loop:
            self._sems[which] = (loop, asyncio.Semaphore(self.max_parallel if which == "gpu" else 2))
        return self._sems[which][1]

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
    def saved_count(self) -> int:
        """Answers saved for the demo (data/ai/answers.jsonl): shown even while the GPU is off."""
        if self.saved_file is None or not self.saved_file.exists():
            return 0
        return sum(1 for line in self.saved_file.read_text(encoding="utf-8").splitlines() if line.strip())

    async def status(self, max_age: float = 30.0) -> dict:
        now = await self._status_now(max_age)
        if not now.get("online") and self.backup_configured:      # our GPU is off: the hosted backup answers
            now = {"online": True, "configured": True, "model": self.backup_model, "mode": "backup", "gpu_error": now.get("error")}
        return {**now, "saved": self.saved_count() if self.cache_enabled else 0}

    async def _status_now(self, max_age: float) -> dict:
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

    def _backup_payload(self, payload: dict) -> dict:
        """The same request for the hosted backup: its model id, and Groq's switch for Qwen thinking instead of vLLM's."""
        body = {k: v for k, v in payload.items() if k != "chat_template_kwargs"}
        body["model"] = self.backup_model
        if "chat_template_kwargs" in payload and "qwen" in self.backup_model.lower():
            body["reasoning_effort"] = "none"
        return body

    async def chat(self, messages: list[dict], *, json_schema: dict | None = None, max_tokens: int = 700,
                   temperature: float = 0.2, cache: bool = True, accept: Callable[[str], bool] | None = None,
                   backup: bool = True) -> str:
        """The model's answer. With `cache`, a request seen before can be answered from the cache, and a new answer is
        kept when `accept` (e.g. a guardrail) passes it: a rejected answer is never replayed, the next try asks again.
        Live-first (the web app): our GPU answers whenever it is on; while it is off, an answer kept from before, else
        the hosted backup (unless `backup=False`). Otherwise (batch scripts): the cache first, then our GPU."""
        payload = self.payload(messages, json_schema=json_schema, max_tokens=max_tokens, temperature=temperature)
        if self.live_first:
            if (await self._status_now(30.0)).get("online"):
                try:
                    content = await self._ask("gpu", payload)
                except LLMUnavailable:
                    content = None                      # it went away just now: answer as if it were off
                if content is not None:
                    if cache and not _passes(accept, content) and (kept := self.cached(payload)) is not None:
                        return self._answered(kept, self.model, "saved")    # the live draft failed its check
                    if cache and _passes(accept, content):
                        self._remember(payload, content)
                    return self._answered(content, self.model, "gpu")
            if cache and (hit := self.cached(payload)) is not None:
                return self._answered(hit, self.model, "saved")
        else:
            if cache and (hit := self.cached(payload)) is not None:
                return self._answered(hit, self.model, "saved")
            if (await self._status_now(30.0)).get("online"):
                content = await self._ask("gpu", payload)
                if cache and _passes(accept, content):
                    self._remember(payload, content)
                return self._answered(content, self.model, "gpu")
        if backup and self.backup_configured:
            body = self._backup_payload(payload)
            if cache and (hit := self.cached(body)) is not None:
                return self._answered(hit, self.backup_model, "saved")
            content = await self._ask("backup", body)
            if cache and _passes(accept, content):
                self._remember(body, content)
            return self._answered(content, self.backup_model, "backup")
        if not self.configured:
            raise LLMUnavailable("LLM_BASE_URL is not set")
        raise LLMUnavailable(f"the model is offline ({self._status.get('error', 'no answer')})")

    async def _ask(self, which: str, body: dict) -> str:
        """One request to our GPU ("gpu") or the hosted backup ("backup")."""
        url, key = (self.base_url, config.LLM_API_KEY) if which == "gpu" else (self.backup_url, config.LLM_BACKUP_API_KEY)
        try:
            async with self._semaphore(which):
                async with self._client(self.timeout) as client:
                    resp = await client.post(f"{url}/chat/completions", json=body,
                                             headers={"Authorization": f"Bearer {key}"} if key else {})
                    if resp.status_code == 429:
                        raise LLMUnavailable("busy: too many requests to the model; try again in a minute")
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            if which == "gpu":
                self._status = {}                       # look again next time: it may have been switched off
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc

    @staticmethod
    def _answered(content: str, model: str, source: str) -> str:
        ANSWERED_BY.set(model)
        ANSWER_SOURCE.set(source)
        return content


def _passes(accept: Callable[[str], bool] | None, content: str) -> bool:
    if accept is None:
        return True
    try:
        return bool(accept(content))
    except Exception:
        return False


llm = LLMClient(backup=True, live_first=True)    # the web app's client; batch scripts make their own, without the backup

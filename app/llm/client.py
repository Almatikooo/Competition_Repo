"""Minimal client for any OpenAI-compatible chat endpoint.

Works with vLLM on a RunPod pod  (LLM_BASE_URL=https://<POD_ID>-8000.proxy.runpod.net/v1),
RunPod Serverless vLLM            (LLM_BASE_URL=https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1),
or a local Ollama / LM Studio server. When nothing is configured the app runs in rule-based mode.
"""
import time

import httpx

from .. import config


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = config.LLM_BASE_URL
        self.model = config.LLM_MODEL
        self.transport = transport  # tests inject httpx.MockTransport here
        self._status: dict = {}
        self._checked_at = 0.0

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self.transport)

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}

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

    async def chat(self, messages: list[dict], *, json_schema: dict | None = None,
                   max_tokens: int = 700, temperature: float = 0.2) -> str:
        if not self.configured:
            raise LLMUnavailable("LLM_BASE_URL is not set")
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if config.LLM_DISABLE_THINKING:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if json_schema:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "output", "schema": json_schema, "strict": True}}
        try:
            async with self._client(config.LLM_TIMEOUT) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            self._status = {}
            raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc


llm = LLMClient()

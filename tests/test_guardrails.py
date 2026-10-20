"""The language model may never invent jobs, courses or statistics. These tests use a fake
OpenAI-compatible (vLLM-style) endpoint, so they run without a GPU."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.catalog import get_catalog
from app.llm import tasks
from app.llm.client import llm
from app.main import app

catalog = get_catalog()
CV = "Handled accounts payable, monthly bank reconciliation and payroll using AutoCount and Excel pivot tables."


@pytest.fixture
def fake_llm(monkeypatch):
    """Points the shared client at an in-process fake vLLM server and records request payloads."""
    calls = []
    replies = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "fake-qwen"}]})
        body = json.loads(request.content)
        calls.append(body)
        kind = "skills" if "skills" in body["response_format"]["json_schema"]["schema"]["properties"] else "explain"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(replies[kind])}}]})

    monkeypatch.setattr(llm, "base_url", "http://fake-vllm/v1")
    monkeypatch.setattr(llm, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(llm, "_status", {})
    return calls, replies


def test_skill_guard_keeps_verbatim_evidence_and_drops_inventions():
    kept, rejected = tasks.guard_skills(catalog, CV, [
        {"id": "bookkeeping", "level": 3, "evidence": "monthly bank reconciliation"},
        {"id": "machine_learning", "level": 3, "evidence": "trained neural networks"},
        {"id": "quantum_poetry", "level": 2, "evidence": "payroll"},
    ])
    assert [k["id"] for k in kept] == ["bookkeeping"]
    assert {r["reason"] for r in rejected} == {"evidence not found in CV", "unknown skill id"}


def test_explanation_guard_rejects_invented_numbers_and_citations():
    facts = {"fit_pct": 54, "outlook_pct_per_year": 12.8, "sdg_targets": [{"target": "8.2"}],
             "sources": [{"id": "S1"}, {"id": "S2"}]}
    assert tasks.guard_explanation("You cover 54% [S1] and demand may grow 12.8% a year [S2], SDG 8.2.", facts) == []
    assert any("numbers" in p for p in tasks.guard_explanation("Salaries rise 35% [S1].", facts))
    assert any("unknown citations" in p for p in tasks.guard_explanation("You cover 54% [S9].", facts))
    assert "no citations" in tasks.guard_explanation("You cover 54%.", facts)


def test_extraction_request_is_schema_constrained_to_catalog_ids(fake_llm):
    calls, replies = fake_llm
    replies["skills"] = {"skills": [{"id": "excel", "level": 2, "evidence": "Excel pivot tables"},
                                    {"id": "python", "level": 3, "evidence": "Python at Google"}]}
    kept, rejected = asyncio.run(tasks.extract_skills(catalog, CV))
    assert [k["id"] for k in kept] == ["excel"] and len(rejected) == 1
    req = calls[0]
    schema = req["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]["skills"]["items"]["properties"]["id"]["enum"]) == set(catalog.skills)
    assert req["chat_template_kwargs"] == {"enable_thinking": False}


def test_api_falls_back_to_template_when_model_invents_a_number(fake_llm):
    _, replies = fake_llm
    replies["explain"] = {"explanation": "This role pays RM 9,999 more [S1]."}
    p = catalog.personas["personas"][0]
    body = {"profile": {"skills": p["skills"]}, "role_id": "data_analyst", "lang": "en"}
    res = TestClient(app).post("/api/explain", json=body).json()
    assert res["engine"] == "template"
    assert res["guardrail"]["rejected"] is True


def test_api_accepts_a_grounded_model_explanation(fake_llm):
    _, replies = fake_llm
    replies["explain"] = {"explanation": "You already have a solid base for this role [S1]. It is an estimate; the decision is yours."}
    p = catalog.personas["personas"][0]
    body = {"profile": {"skills": p["skills"]}, "role_id": "data_analyst", "lang": "en"}
    res = TestClient(app).post("/api/explain", json=body).json()
    assert res["engine"] == "llm" and res["guardrail"] == {"rejected": False}


def test_cv_parse_uses_model_but_keeps_guardrail(fake_llm):
    _, replies = fake_llm
    replies["skills"] = {"skills": [{"id": "bookkeeping", "level": 3, "evidence": "accounts payable"},
                                    {"id": "cybersecurity", "level": 3, "evidence": "ran a SOC team"}]}
    res = TestClient(app).post("/api/profile/parse", data={"text": CV}).json()
    ids = {s["id"] for s in res["skills"]}
    assert res["engine"] == "llm" and "bookkeeping" in ids and "cybersecurity" not in ids
    assert res["rejected_by_guardrail"] == 1

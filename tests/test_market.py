"""Part 4: the job market for one direction, from the facts the model read in the postings — and the model's short
market check, which may only use numbers from those statistics. A fake vLLM endpoint stands in for the GPU."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import opportunities as opp
from app.engine.matching import Profile
from app.llm.client import llm
from app.main import app

client = TestClient(app)


def posting(i, **ai):
    return {"id": f"j{i}", "title": "Data Analyst", "url": f"https://x.example/{i}", "roles": ["data_analyst"], "countries": ["MY"],
            "remote": None, "ai": ai}


def test_market_stats_count_what_postings_require():
    jobs = [posting(1, req=["sql", "excel"], years=2, degree="bachelor", degree_required=True, languages=["en"], pay=[4000, 6000, "MYR", "month"]),
            posting(2, req=["sql"], nice=["python"], years=5, mode="hybrid", pay=[5000, None, "MYR", "month"], visa=False),
            posting(3, req=["sql", "data_viz"], years=8, degree="bachelor", degree_required=False, pay=[4500, 7000, "MYR", "month"]),
            posting(4, req=["excel"], languages=["en", "ms"], pay=[3000, 4000, "MYR", "month"], visa=True),
            posting(5, req=["sql"], pay=[6000, 9000, "MYR", "month"])]
    stats = opp.market_stats(jobs, Profile(skills={"sql": 2, "python": 3}))
    assert stats["n"] == 5 and stats["read"] == 5
    assert [(s["id"], s["share"], s["you"]) for s in stats["skills"]] == [("sql", 0.8, True), ("excel", 0.4, False), ("data_viz", 0.2, False)]
    assert stats["coverage"] == round(0.8 / 1.4, 3)
    assert stats["years"] == {"n": 3, "median": 5, "share_0_2": round(1 / 3, 3), "share_3_5": round(1 / 3, 3), "share_6_plus": round(1 / 3, 3)}
    assert stats["degree_share"] == 0.2                       # one requires a degree; the other only prefers one
    assert stats["languages"][0] == {"code": "en", "share": 0.4}
    assert stats["pay"] == {"currency": "MYR", "per": "month", "n": 5, "low": 4500, "high": 6000}
    assert stats["visa"] == {"sponsors": 1, "no": 1} and stats["modes"] == {"hybrid": 1.0}


def test_too_few_postings_here_means_the_picture_is_drawn_worldwide():
    profile = {"skills": {"excel": 2, "bookkeeping": 3}, "years_experience": 9, "languages": ["ms", "en"]}
    res = client.post("/api/next/market", json={"profile": profile, "country": "MY", "role": "financial_analyst"}).json()
    assert res["here"]["read"] < opp.MIN_LOCAL_SAMPLE and res["basis"] == "world"
    assert res["world"]["n"] > 50 and res["world"]["skills"] and res["outlook_pct"] is not None
    big = client.post("/api/next/market", json={"profile": profile, "country": "US", "role": "software_developer"}).json()
    assert big["basis"] == "here" and big["here"]["n"] > opp.MIN_LOCAL_SAMPLE
    assert client.post("/api/next/market", json={"profile": profile, "country": "MY", "role": "astronaut"}).status_code == 404
    rare = min(opp.get_catalog().roles, key=lambda r: sum(1 for j in opp.data()["jobs"] if r in j["roles"]))
    thin = client.post("/api/next/market", json={"profile": profile, "country": "DE", "role": rare}).json()
    assert thin["world"]["read"] < opp.MIN_WORLD_SAMPLE and thin["basis"] == "none"      # no percentages of two postings
    assert client.post("/api/next/market/ai", json={"profile": profile, "country": "DE", "role": rare}).json()["engine"] is None


@pytest.fixture
def fake_check(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "fake-qwen"}]})
        seen["facts"] = json.loads(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"check": seen["text"]})}}]})

    monkeypatch.setattr(llm, "base_url", "http://fake-vllm/v1")
    monkeypatch.setattr(llm, "transport", httpx.MockTransport(handler))
    return seen


def test_the_market_check_uses_only_the_statistics(fake_check):
    body = {"profile": {"skills": {"sql": 2}, "years_experience": 2}, "country": "MY", "role": "data_analyst", "country_name": "Malaysia"}
    stats = client.post("/api/next/market", json=body).json()
    top = stats[stats["basis"]]["skills"][0]
    fake_check["text"] = f"About {round(100 * top['share'])}% of these postings ask for the top skill, so start there."
    good = client.post("/api/next/market/ai", json=body).json()
    assert good["engine"] == "llm" and good["text"].startswith("About")
    assert fake_check["facts"]["where"] == "Malaysia" and fake_check["facts"]["person"]["years_of_experience"] == 2
    fake_check["text"] = "Salaries here average 12345 a month."
    bad = client.post("/api/next/market/ai", json=body).json()
    assert bad["engine"] is None and bad["guardrail"]["rejected"]

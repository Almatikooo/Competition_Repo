"""Part 3: postings are matched against what they explicitly ask for (read by the model): required skills count more
than nice-to-haves, and missing experience or languages lower the fit and are named. The model's short advice on a
posting may only use numbers from the posting's facts. A fake vLLM endpoint stands in for the GPU."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import opportunities as opp
from app.engine.matching import Profile
from app.llm import tasks
from app.llm.client import llm
from app.main import app

client = TestClient(app)
JOB = {"id": "j999999", "title": "Finance Data Analyst", "company": "Acme", "url": "https://acme.example/jobs/1", "location": "Kuala Lumpur",
       "level": "mid", "countries": ["MY"], "remote": None, "roles": ["data_analyst"], "skills": ["sql", "excel", "python"],
       "ai": {"req": ["sql", "excel"], "nice": ["python"], "years": 5, "languages": ["en", "de"], "pay": [6000, 8000, "MYR", "month"]}}
SKILLS = {"sql": 2, "excel": 3, "data_analysis": 2}


def score(**profile):
    return opp.score_job(Profile(skills=SKILLS, **profile), set(), JOB, ["data_analyst"], {})


def check(result, kind):
    return next(c for c in result["checks"] if c["kind"] == kind)


def test_experience_and_languages_are_checked_only_when_the_person_said():
    unknown = score()
    assert check(unknown, "years") == {"kind": "years", "need": 5, "have": None, "ok": None}
    assert check(unknown, "languages")["ok"] is None and check(unknown, "skills") == {"kind": "skills", "have": 2, "of": 2, "ok": True}
    meets = score(years_experience=6, languages=["en", "de", "ms"])
    assert check(meets, "years")["ok"] and check(meets, "languages")["ok"] and meets["fit"] == unknown["fit"]
    short = score(years_experience=2, languages=["en", "ms"])
    assert check(short, "years") == {"kind": "years", "need": 5, "have": 2, "ok": False}
    assert check(short, "languages")["missing"] == ["de"]
    assert short["fit"] == max(0, unknown["fit"] - round(100 * (min(opp.YEAR_PENALTY_CAP, 3 * opp.YEAR_PENALTY) + opp.LANGUAGE_PENALTY)))


def test_required_skills_count_more_than_nice_to_haves():
    base = Profile(skills={"python": 3})                  # has only the nice-to-have
    other = Profile(skills={"sql": 3})                    # has a required skill
    a = opp.score_job(base, set(), {**JOB, "roles": []}, [], {})
    b = opp.score_job(other, set(), {**JOB, "roles": []}, [], {})
    assert b["fit"] > a["fit"]
    assert [m["id"] for m in a["missing"]][:2] == ["excel", "sql"] or {m["id"] for m in a["missing"][:2]} == {"sql", "excel"}
    assert "python" not in {m["id"] for m in b["missing"]}   # a missing nice-to-have is not shown as a gap


def test_profile_extras_never_change_the_role_ranking():
    plain = client.post("/api/match", json={"profile": {"skills": SKILLS}}).json()["roles"]
    extra = client.post("/api/match", json={"profile": {"skills": SKILLS, "years_experience": 30, "languages": ["de"]}}).json()["roles"]
    assert [(r["id"], r["total"]) for r in plain] == [(r["id"], r["total"]) for r in extra]


def test_numbers_are_compared_as_written():
    assert tasks.numbers_in("RM4,500 a month, 3,5 days, 4.0 h") == {"4500", "3.5", "4"}
    assert tasks.guard_numbers("Pay is RM6,000 to RM8,000.", {"pay": [6000, 8000]}) == []
    assert tasks.guard_numbers("About 100 hours.", {"hours": 1}) != []        # 100 is not 1


# ---------------------------------------------------------------- the model's advice on one posting
@pytest.fixture
def fake_advice(monkeypatch):
    replies = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "fake-qwen"}]})
        body = json.loads(request.content)
        replies["facts"] = json.loads(body["messages"][1]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"advice": replies["text"]})}}]})

    monkeypatch.setattr(llm, "base_url", "http://fake-vllm/v1")
    monkeypatch.setattr(llm, "transport", httpx.MockTransport(handler))
    return replies


def test_advice_uses_only_the_postings_facts(fake_advice):
    job = next(j for j in opp.data()["jobs"] if j.get("ai", {}).get("years"))
    body = {"profile": {"skills": SKILLS, "years_experience": 1, "languages": ["en"]}, "job_id": job["id"], "lang": "en"}
    fake_advice["text"] = f"It asks for {job['ai']['years']} years and you have 1, so start with a smaller role."
    good = client.post("/api/next/why", json=body).json()
    assert good["engine"] == "llm" and good["text"].startswith("It asks for")
    facts = fake_advice["facts"]
    assert facts["posting_asks"]["years_of_experience"] == job["ai"]["years"] and facts["person"]["years_of_experience"] == 1
    fake_advice["text"] = "You would earn 9999 a month here."
    bad = client.post("/api/next/why", json=body).json()
    assert bad["engine"] is None and bad["guardrail"]["rejected"]
    assert client.post("/api/next/why", json={**body, "job_id": "j0"}).status_code == 404
    assert client.post("/api/next/why", json={**body, "job_id": "x1"}).status_code == 422


def test_advice_without_a_model_says_so():
    job = opp.data()["jobs"][0]
    res = client.post("/api/next/why", json={"profile": {"skills": SKILLS}, "job_id": job["id"]}).json()
    assert res["engine"] is None and "not set" in res["error"]


def test_a_language_named_in_the_title_is_required():
    assert opp.title_languages("KYC/KYB Analyst - Japanese Speaker") == ["ja"]
    assert opp.title_languages("Finnish Tech Linguistic Tester") == ["fi"]
    assert opp.title_languages("Bilingual Account Executive (Spanish)") == ["es"]
    assert opp.title_languages("Bahasa Indonesia Content Writer") == ["id"]
    assert opp.title_languages("Thailand Sales Lead") == [] and opp.title_languages("Data Analyst") == []
    tester = {**JOB, "title": "Finnish Tech Linguistic Tester", "ai": {**JOB["ai"], "languages": ["en"]}}
    res = opp.score_job(Profile(skills=SKILLS, languages=["en", "ms"]), set(), tester, [], {})
    assert check(res, "languages")["missing"] == ["fi"]


def test_postings_with_a_saved_ai_answer_are_marked_while_the_gpu_is_off(tmp_path, monkeypatch):
    profile = {"skills": {"bookkeeping": 3, "excel": 2, "data_entry": 3, "finance_domain": 1}, "years_experience": 9, "languages": ["ms", "en"]}
    body = {"profile": profile, "country": "MY", "roles": ["financial_analyst", "accounting_clerk"], "lang": "en"}
    first = client.post("/api/next/jobs", json=body).json()["local"][0]
    facts = opp.advice_facts(Profile(**profile), [], opp.job_by_id(first["id"]))
    key = llm._key(tasks.advice_payload(facts, "en"))
    saved = tmp_path / "answers.jsonl"
    saved.write_text(json.dumps({"k": key, "v": json.dumps({"advice": "A saved answer."})}) + "\n")
    monkeypatch.setattr(llm, "cache_enabled", True)
    monkeypatch.setattr(llm, "saved_file", saved)
    monkeypatch.setattr(llm, "cache_file", None)
    monkeypatch.setattr(llm, "_answers", None)
    res = client.post("/api/next/jobs", json=body).json()
    marks = {j["id"]: j.get("advice_saved") for j in res["local"][:12]}
    assert marks[first["id"]] is True and sum(1 for v in marks.values() if v) == 1
    why = client.post("/api/next/why", json={"profile": profile, "job_id": first["id"], "lang": "en"}).json()
    assert why == {"engine": "llm", "text": "A saved answer.", "model": llm.model}      # no GPU needed

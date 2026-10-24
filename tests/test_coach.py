"""The career coach: it sees the person's whole journey (profile, top roles, courses, plans, jobs where they look), links
only to pages it was offered, and still answers while the GPU is off, through the hosted backup. A CV never goes there."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.advisor import COACH_OPTIONS, coach_facts
from app.catalog import get_catalog
from app.engine.matching import Profile, Weights
from app.learn import get_learn
from app.llm.client import LLMClient, LLMUnavailable, llm
from app.main import LearningProgress, app, outlook_for, resolve_as_of

client = TestClient(app)
catalog = get_catalog()
AISYAH = next(p for p in catalog.personas["personas"] if p["id"] == "aisyah")
PROFILE = {k: AISYAH.get(k) for k in ("skills", "interests", "sdg_priorities", "current_role", "hours_per_week", "years_experience", "languages")}
ASK = [{"role": "user", "content": "What should I do first?"}]


def facts_for(profile: dict, learning=None, certified=(), plans=None) -> dict:
    return coach_facts(catalog, get_learn(), outlook_for(resolve_as_of(None)), Profile(**profile), Weights(), "moderate", "MY",
                       learning or {}, list(certified), plans or {})


def test_the_coach_sees_the_whole_journey():
    facts = facts_for({**PROFILE, "current_role": "data_entry_clerk"}, learning={"sql": LearningProgress(done=3, chapters=1),
                      "excel": LearningProgress()}, certified=["data_entry"], plans={"data_analyst": ["sql"]})
    assert len(facts["top_options"]) == COACH_OPTIONS
    assert facts["person"]["current_job_outlook_from_employers_in_malaysia"]["net_change_percent_by_2030"] == -28
    sql = next(c for c in facts["their_courses"] if c["course"] == catalog.skills["sql"]["name"]["en"])
    assert sql == {"course": sql["course"], "lessons_done": 3, "lessons_total": len(get_learn().courses["sql"]["lessons"]),
                   "chapter_tests_passed": 1, "chapters": len(get_learn().courses["sql"]["modules"]), "certificate": False}
    assert [c["certificate"] for c in facts["their_courses"]] == [True, False]       # a course never started is left out
    plan = facts["their_plans"][0]
    assert plan["role"] == catalog.roles["data_analyst"]["title"]["en"] and plan["steps_done"] >= 1 and plan["next_steps"]
    jobs = facts["open_jobs_where_they_look"]
    offer = facts["links_you_can_offer"]
    assert jobs and all(j["id"] in offer for j in jobs)
    assert {"plan:data_analyst", "course:sql", "jobs", "learn"} <= set(offer)


@pytest.fixture
def fake_coach(monkeypatch):
    state = {"reply": {"answer": "Start with your plan.", "links": []}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "fake-qwen"}]})
        state["last"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(state["reply"])}}]})

    monkeypatch.setattr(llm, "base_url", "http://fake-vllm/v1")
    monkeypatch.setattr(llm, "transport", httpx.MockTransport(handler))
    return state


def test_the_coach_links_only_to_pages_it_was_offered(fake_coach):
    job = facts_for(PROFILE)["open_jobs_where_they_look"][0]["id"]
    fake_coach["reply"] = {"answer": "Open your plan, then look at this job.", "links": ["plan:data_analyst", job, "plan:astronaut", "plan:data_analyst"]}
    res = client.post("/api/chat", json={"profile": PROFILE, "messages": ASK, "context": {"plans": {"data_analyst": []}}}).json()
    assert res["engine"] == "llm" and [x["kind"] for x in res["links"]] == ["plan", "job"]
    assert res["links"][1]["url"].startswith("https://") and res["links"][1]["title"]
    enum = fake_coach["last"]["response_format"]["json_schema"]["schema"]["properties"]["links"]["items"]["enum"]
    assert "plan:data_analyst" in enum and job in enum and "plan:astronaut" not in enum


def backup_on(monkeypatch, handler):
    monkeypatch.setattr(llm, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(llm, "backup_url", "https://backup.example/openai/v1")
    monkeypatch.setattr(config, "LLM_BACKUP_API_KEY", "test-key")


def test_while_the_gpu_is_off_the_hosted_backup_answers(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), body=json.loads(request.content), auth=request.headers.get("authorization"))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"answer": "Start with SQL.", "links": []})}}]})

    backup_on(monkeypatch, handler)
    assert client.get("/api/meta").json()["llm"]["mode"] == "backup"
    res = client.post("/api/chat", json={"profile": PROFILE, "messages": ASK}).json()
    assert res["engine"] == "llm" and res["model"] == llm.backup_model
    assert seen["url"] == "https://backup.example/openai/v1/chat/completions" and seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == llm.backup_model and "chat_template_kwargs" not in seen["body"]
    assert seen["body"]["reasoning_effort"] == "none"                                  # Groq's switch for Qwen thinking


def test_a_busy_backup_says_so(monkeypatch):
    backup_on(monkeypatch, lambda request: httpx.Response(429, json={"error": {"message": "rate limit"}}))
    res = client.post("/api/chat", json={"profile": PROFILE, "messages": ASK}).json()
    assert res["engine"] is None and "busy" in res["error"]


def test_a_cv_never_goes_to_the_backup(monkeypatch):
    calls = []
    backup_on(monkeypatch, lambda request: calls.append(str(request.url)) or httpx.Response(502))
    monkeypatch.setattr(llm, "base_url", "http://fake-vllm/v1")             # our GPU is configured, but switched off
    res = client.post("/api/profile/parse", data={"text": AISYAH["cv_text"]}).json()
    assert res["engine"] == "rules" and res["skills"]
    assert not [u for u in calls if "backup.example" in u]


def test_a_saved_answer_beats_the_backup(tmp_path, monkeypatch):
    answers = {"n": 0}

    def gpu(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": "from our GPU"}}]})

    def gpu_off_backup_on(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(502)
        answers["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "from the backup"}}]})

    def make(transport) -> LLMClient:
        c = LLMClient(transport=httpx.MockTransport(transport), cache_dir=tmp_path / "llm", saved=tmp_path / "saved.jsonl", backup=True)
        c.base_url, c.backup_url = "http://fake-vllm/v1", "https://backup.example/v1"
        return c

    monkeypatch.setattr(config, "LLM_BACKUP_API_KEY", "k")
    assert asyncio.run(make(gpu).chat(ASK)) == "from our GPU"                       # kept while the GPU was on
    later = make(gpu_off_backup_on)
    assert asyncio.run(later.chat(ASK)) == "from our GPU" and answers["n"] == 0
    assert asyncio.run(later.chat([{"role": "user", "content": "Something new"}])) == "from the backup"
    with pytest.raises(LLMUnavailable, match="offline"):
        asyncio.run(later.chat([{"role": "user", "content": "My CV"}], backup=False))

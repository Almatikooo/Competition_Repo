"""Reading job postings with the model: the trimming, the guard that drops invented facts, and a full (fake-GPU)
run that saves progress and continues after the GPU stops."""
import asyncio
import json

import httpx
import pytest

from app.llm.client import LLMClient
from scripts.opportunities import enrich
from scripts.opportunities.trim import sentences, text_hash, trim, url_key

SKILLS = {"sql", "python", "excel", "bookkeeping", "data_analysis"}
POSTING = [
    "We are a fast-growing fintech with offices across Asia.",                                  # 1
    "Requirements: Diploma or Degree in Accounting.",                                           # 2
    "At least 2 years of experience in accounts payable.",                                      # 3
    "Strong Excel skills; SQL is a plus.",                                                      # 4
    "Fluent in English and Bahasa Malaysia.",                                                   # 5
    "Salary: RM3,500 - RM4,500 per month.",                                                     # 6
    "Hybrid: 3 days in our Kuala Lumpur office.",                                               # 7
    "We are unable to sponsor work visas.",                                                     # 8
]
ANSWER = {
    "skills": [{"id": "bookkeeping", "need": "required", "s": 3}, {"id": "excel", "need": "required", "s": 4},
               {"id": "sql", "need": "nice", "s": 4}],
    "years": {"min": 2, "s": 3}, "degree": {"level": "diploma", "required": True, "s": 2},
    "languages": [{"code": "en", "s": 5}, {"code": "ms", "s": 5}],
    "pay": {"min": 3500, "max": 4500, "currency": "MYR", "per": "month", "s": 6},
    "mode": {"value": "hybrid", "s": 7}, "visa": {"sponsors": False, "s": 8},
}
FACTS = {"req": ["bookkeeping", "excel"], "nice": ["sql"], "years": 2, "degree": "diploma", "degree_required": True,
         "languages": ["en", "ms"], "pay": [3500, 4500, "MYR", "month"], "mode": "hybrid", "visa": False}


# ---------------------------------------------------------------- trimming
def test_trim_keeps_terms_and_requirements_and_drops_boilerplate():
    text = ("Acme is a world leader in widgets and our mission is to delight customers. "
            "You will build data pipelines in Python and Node.js. Requirements: 3+ years of SQL. "
            "Base pay range: $120k - $150k. We offer health insurance, dental and paid time off. "
            "Acme is an equal opportunity employer. Visa sponsorship is available.")
    kept = trim(text)
    assert "Requirements: 3+ years of SQL." in kept and "Base pay range: $120k - $150k." in kept
    assert "Visa sponsorship is available." in kept and "You will build data pipelines in Python and Node.js." in kept
    assert not any("health insurance" in s or "equal opportunity" in s or "world leader" in s for s in kept)
    assert sum(len(s) for s in trim(text * 40)) <= 2500                      # capped
    assert sentences("Senior Node.js dev, 4.5k RM. Next one") == ["Senior Node.js dev, 4.5k RM.", "Next one"]
    assert sentences("要求：本科以上学历。三年以上经验。") == ["要求：本科以上学历。", "三年以上经验。"]


def test_stable_keys_and_text_hashes():
    assert url_key("https://jobs.example.com/1") == url_key("https://jobs.example.com/1") != url_key("https://jobs.example.com/2")
    assert len(url_key("https://x")) == 16 and text_hash(["a"]) != text_hash(["b"])


# ---------------------------------------------------------------- the guard
def test_guard_keeps_grounded_facts():
    facts, dropped = enrich.guard(POSTING, ANSWER, SKILLS)
    assert facts == FACTS and dropped == []


@pytest.mark.parametrize("change, lost", [
    ({"years": {"min": 5, "s": 3}}, "years"),                                     # 5 is not in sentence 3
    ({"years": {"min": 2, "s": 99}}, "years"),                                    # no sentence 99
    ({"pay": {"min": 3500, "max": 6000, "currency": "MYR", "per": "month", "s": 6}}, "pay"),   # 6000 is invented
    ({"pay": {"min": 3500, "max": 4500, "currency": "SGD", "per": "month", "s": 6}}, "pay"),   # the sentence says RM
    ({"degree": {"level": "master", "required": True, "s": 2}}, "degree"),       # sentence 2 says diploma/degree
    ({"mode": {"value": "remote", "s": 7}}, "mode"),
    ({"visa": {"sponsors": True, "s": 6}}, "visa"),                              # sentence 6 is about pay
])
def test_guard_drops_what_the_cited_sentence_does_not_say(change, lost):
    facts, dropped = enrich.guard(POSTING, {**ANSWER, **change}, SKILLS)
    assert lost not in facts and lost in dropped
    assert {k: v for k, v in facts.items() if k != lost and not (lost == "degree" and k == "degree_required")} == \
           {k: v for k, v in FACTS.items() if k != lost and not (lost == "degree" and k == "degree_required")}


def test_guard_drops_unknown_skills_and_unmentioned_languages():
    answer = {**ANSWER, "skills": ANSWER["skills"] + [{"id": "quantum_magic", "need": "required", "s": 4}],
              "languages": [{"code": "en", "s": 5}, {"code": "de", "s": 5}]}
    facts, dropped = enrich.guard(POSTING, answer, SKILLS)
    assert "quantum_magic" not in facts["req"] and facts["languages"] == ["en"]
    assert "skill:quantum_magic" in dropped and "language:de" in dropped


def test_guard_understands_k_amounts_number_words_and_malay():
    sents = ["Base salary $120k-$150k per year.", "Minimum three years in a similar role.", "Pengalaman sekurang-kurangnya dua tahun."]
    answer = {"skills": [], "years": {"min": 3, "s": 2}, "degree": None, "languages": [],
              "pay": {"min": 120000, "max": 150000, "currency": "USD", "per": "year", "s": 1}, "mode": None, "visa": None}
    facts, _ = enrich.guard(sents, answer, SKILLS)
    assert facts == {"years": 3, "pay": [120000, 150000, "USD", "year"]}
    assert enrich.guard(sents, {**answer, "years": {"min": 2, "s": 3}}, SKILLS)[0]["years"] == 2


def test_schema_constrains_ids_and_codes():
    s = enrich.schema(sorted(SKILLS))
    assert s["properties"]["skills"]["items"]["properties"]["id"]["enum"] == sorted(SKILLS)
    assert set(s["required"]) == {"skills", "years", "degree", "languages", "pay", "mode", "visa"}
    assert "MYR" in s["properties"]["pay"]["anyOf"][0]["properties"]["currency"]["enum"]


# ---------------------------------------------------------------- a full run on a fake GPU
@pytest.fixture
def workspace(tmp_path, monkeypatch):
    rows = [{"key": f"k{i}", "id": f"j{i}", "title": f"Accounts Executive {i}", "company": "Acme", "sentences": POSTING,
             "h": text_hash(POSTING)} for i in range(1, 6)]
    rows.append({"key": "k6", "id": "j6", "title": "Empty", "company": "Acme", "sentences": [], "h": text_hash([])})
    jobs = [{"id": f"j{i}", "countries": ["MY"] if i == 5 else ["US"], "remote": None, "posted": f"2026-10-0{i}"} for i in range(1, 7)]
    (tmp_path / "texts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "jobs.json").write_text(json.dumps({"jobs": jobs}))
    for name, path in {"TEXTS": "texts.jsonl", "PROGRESS": "progress.jsonl", "JOBS": "jobs.json", "OUT": "job_facts.json", "GOLD": "gold.json"}.items():
        monkeypatch.setattr(enrich, name, tmp_path / path)
    monkeypatch.setattr(enrich, "ROOT", tmp_path)
    return tmp_path


def fake_gpu(online=True, fail_after=None):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200 if online and (fail_after is None or len(seen) < fail_after) else 502, json={"data": [{"id": "q"}]})
        if fail_after is not None and len(seen) >= fail_after:
            return httpx.Response(502)
        body = json.loads(request.content)
        seen.append(body["messages"][1]["content"].split("\n")[0])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(ANSWER)}}]})

    client = LLMClient(transport=httpx.MockTransport(handler), max_parallel=2, cache_dir=None)
    client.base_url = "http://fake-vllm/v1"
    return client, seen


def test_a_run_reads_by_priority_saves_facts_and_skips_what_it_read(workspace):
    client, seen = fake_gpu()
    stats = asyncio.run(enrich.run(None, 1, client))
    assert stats["done"] == 5 and seen[0] == "Job title: Accounts Executive 5"      # the Malaysian posting first
    out = json.loads((workspace / "job_facts.json").read_text())
    assert out["read"] == 5 and out["facts"]["k1"] == FACTS and "k6" not in out["facts"]
    again, seen_again = fake_gpu()
    assert asyncio.run(enrich.run(None, 2, again))["done"] == 0 and not seen_again


def test_a_stopped_gpu_loses_nothing(workspace):
    client, seen = fake_gpu(fail_after=2)
    stats = asyncio.run(enrich.run(None, 1, client))
    assert stats["offline"] and stats["done"] == 2
    rest, seen_rest = fake_gpu()
    assert asyncio.run(enrich.run(None, 2, rest))["done"] == 3 and len(seen_rest) == 3
    assert json.loads((workspace / "job_facts.json").read_text())["read"] == 5


def test_eval_scores_against_the_gold_set(workspace):
    gold = [{"title": "Accounts Executive", "company": "Acme", "sentences": POSTING, "expect": FACTS},
            {"title": "Other", "company": "Acme", "sentences": POSTING, "expect": {**FACTS, "years": 4, "nice": ["sql", "python"]}}]
    (workspace / "gold.json").write_text(json.dumps(gold))
    client, _ = fake_gpu()
    result = asyncio.run(enrich.evaluate(2, client))
    assert result["pay"] == 1.0 and result["years"] == 0.5 and result["skills_precision"] == 1.0 and result["skills_recall"] == 6 / 7


def test_dry_run_estimate_is_in_the_expected_range(workspace):
    rows = enrich.load_rows()
    e = enrich.estimate(enrich.pending(rows, {}), 900)
    assert e["postings"] == 5 and 0 < e["hours"] < 0.01 and e["cost"] < 0.01

import json
import re
import shutil
import subprocess
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalog import get_catalog
from app.learn import (CHAPTER_PASS, CHAPTER_QUESTIONS, FINAL_PASS, FINAL_QUESTIONS, LEARN_DIR, MIN_CHAPTER_POOL, MIN_COURSE_POOL,
                       TEST_RULES, LearnError, clean_name, get_learn, issue_certificate, sign, verify_certificate)
from app.main import app

client = TestClient(app)
learn = get_learn()
catalog = get_catalog()
ROOT = Path(__file__).resolve().parents[1]
OPEN_LICENSES = {"MIT", "CC0 1.0", "CC BY 4.0", "CC BY-SA 4.0", "Open Government Licence v3.0", "Public domain (CC0)",
                 "Public domain (U.S. Government work)", "Design Science License"}


def answers_for(sid, questions, right):
    """Answer the first `right` questions correctly and the rest wrongly."""
    pool = learn.questions[sid]
    return [pool[q["id"]]["answer"] if i < right else (pool[q["id"]]["answer"] + 1) % len(q["options"]) for i, q in enumerate(questions)]


def take(sid, body, right=None):
    attempt = client.post(f"/api/learn/course/{sid}/test", json=body).json()
    n = len(attempt["questions"]) if right is None else right
    return attempt, client.post(f"/api/learn/course/{sid}/test/grade",
                                json={"attempt": attempt["attempt"], "answers": answers_for(sid, attempt["questions"], n)}).json()


def chapter_tokens(sid):
    return [take(sid, {"chapter": n})[1]["token"] for n in range(1, len(learn.courses[sid]["modules"]) + 1)]


def lesson_files():
    return sorted((LEARN_DIR / "lessons").glob("*/*.html"))


# ---------------------------------------------------------------- content

def test_every_skill_has_a_full_course():
    assert learn.problems == []
    assert set(learn.courses) == set(catalog.skills)
    for sid, course in learn.courses.items():
        assert len(course["lessons"]) >= 6, sid
        assert course["minutes"] >= 40, sid
        assert len(course["outcomes"]) >= 3 and len(course["modules"]) >= 2, sid


def test_every_lesson_is_attributed_and_openly_licensed():
    for sid, course in learn.courses.items():
        sources = {s["id"]: s for s in course["sources"]}
        for s in sources.values():
            assert s["license"] in OPEN_LICENSES, (sid, s["license"])
            assert not s["noncommercial"], (sid, s["id"])
            assert s["license_url"].startswith("https://") and s["attribution"], (sid, s["id"])
        for lesson in course["lessons"]:
            assert lesson["source"] in sources and lesson["url"].startswith("https://"), (sid, lesson["id"])
            assert lesson["words"] >= 150, (sid, lesson["id"])


def test_github_sources_are_pinned_to_a_commit():
    pins = json.loads((LEARN_DIR / "pins.json").read_text())
    for sid, course in learn.courses.items():
        for lesson in course["lessons"]:
            m = re.match(r"https://github\.com/([^/]+/[^/]+)/blob/([0-9a-f]{40})/", lesson["url"])
            if lesson["url"].startswith("https://github.com/"):
                assert m and pins[m.group(1)] == m.group(2), (sid, lesson["url"])


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags_of(path):
    parser = _Tags()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.tags


def test_lesson_html_is_sanitised():
    """Lesson HTML is injected into the page, so it must contain only the allowlisted, inert markup."""
    for path in lesson_files():
        for tag, attrs in tags_of(path):
            assert tag not in {"script", "iframe", "style", "object", "embed", "form", "input", "link", "meta"}, (path.name, tag)
            assert not any(a.startswith("on") for a in attrs), (path.name, tag, attrs)
            assert not (attrs.get("href") or "").strip().lower().startswith("javascript:"), (path.name, attrs)
            if tag == "img":
                assert attrs.get("src", "").startswith("https://"), (path.name, attrs.get("src"))


def test_lessons_have_no_leftover_site_chrome():
    chrome = re.compile(r"subscribe to (the|our) [\w ]*(newsletter|insider)|sign up to receive|back to top|was this page helpful|learn more\s+"
                        r"(january|february|march|april|may|june|july|august|september|october|november|december) \d|:::image|\{%|"
                        r"this file may not be suitable for users of assistive", re.I)
    for path in lesson_files():
        text = path.read_text(encoding="utf-8")
        assert not chrome.search(text), (path.name, chrome.search(text).group(0))


def test_heading_ids_cannot_collide_with_the_app():
    for path in lesson_files():
        ids = [(tag, attrs["id"]) for tag, attrs in tags_of(path) if "id" in attrs]
        assert all(tag in ("h2", "h3") and i.startswith("h-") for tag, i in ids), path.name
        assert len(ids) == len({i for _, i in ids}), path.name


def test_question_pools_are_large_grounded_and_balanced():
    """Every chapter can fill its test with spares for a retake, and the final test can draw a fresh mix."""
    positions = Counter()
    for sid, course in learn.courses.items():
        pool = course["pool"]
        per_chapter = Counter(q["module"] for q in pool)
        assert len(pool) >= MIN_COURSE_POOL > FINAL_QUESTIONS, sid
        assert all(per_chapter[i] >= MIN_CHAPTER_POOL > CHAPTER_QUESTIONS for i in range(len(course["modules"]))), (sid, per_chapter)
        assert len({q["id"] for q in pool}) == len(pool), sid
        texts = {}
        for q in pool:
            assert q["module"] == next(i for i, m in enumerate(course["modules"]) if q["lesson"] in m["lessons"]), (sid, q["q"])
            if q.get("origin") != "authored":
                continue
            positions[q["answer"]] += 1
            if q["lesson"] not in texts:
                html = (LEARN_DIR / "lessons" / sid / f"{q['lesson']}.html").read_text(encoding="utf-8")
                texts[q["lesson"]] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).lower()
            words = re.sub(r"\s+", " ", q["evidence"]).lower().split()
            assert all(w.strip("“”‘’\"'.,;:()") in texts[q["lesson"]] for w in words[:3]), (sid, q["q"])
    # guards against an "always option B" bank of questions
    assert len(positions) >= 4 and max(positions.values()) < 0.35 * sum(positions.values())


# ---------------------------------------------------------------- API

def test_course_endpoints_never_leak_answers():
    course = client.get("/api/learn/course/sql").json()
    assert course["title"] == "Databases and SQL" and course["syllabus"] and course["sources"] and course["tests"] == TEST_RULES
    assert "pool" not in course and "answer" not in json.dumps(course)
    attempt = client.post("/api/learn/course/sql/test", json={"chapter": 1}).json()
    assert attempt["total"] == len(attempt["questions"]) == CHAPTER_QUESTIONS and attempt["pass_mark"] == CHAPTER_PASS
    assert all(set(q) == {"id", "q", "options", "lesson", "lesson_title"} for q in attempt["questions"])
    assert client.get("/api/learn/course/nope").status_code == 404
    assert client.post("/api/learn/course/sql/test", json={"chapter": 99}).status_code == 400


def test_lesson_endpoint_serves_text_and_navigation():
    first = client.get("/api/learn/course/python/lesson/python-01").json()
    assert first["index"] == 1 and first["prev"] is None and first["next"] == "python-02"
    assert len(first["html"]) > 1000 and first["source"]["license"] == "CC BY 4.0"
    assert client.get("/api/learn/course/python/lesson/python-99").status_code == 404
    assert client.get("/api/learn/course/python/lesson/sql-01").status_code == 404


def test_courses_list_is_summarised():
    body = client.get("/api/learn/courses").json()
    assert len(body["courses"]) == len(catalog.skills) and body["tests"] == TEST_RULES
    c = next(x for x in body["courses"] if x["skill"] == "excel")
    assert c["lessons"] >= 10 and c["minutes"] > 60 and c["provider"] and c["chapters"] == 4 and "html" not in c


def test_chapter_test_passes_at_four_of_five_and_hides_the_key():
    fail_attempt, fail = take("sql", {"chapter": 2}, right=0)
    assert not fail["passed"] and fail["score"] == 0 and fail["review"] and "token" not in fail
    assert all("answer" not in r for r in fail["results"]), "a chapter test must not reveal the key"
    _, just = take("sql", {"chapter": 2}, right=CHAPTER_PASS)
    assert just["passed"] and just["score"] == 4 and just["token"] and all("answer" not in r for r in just["results"])
    _, below = take("sql", {"chapter": 2}, right=CHAPTER_PASS - 1)
    assert not below["passed"]
    bad = client.post("/api/learn/course/sql/test/grade", json={"attempt": fail_attempt["attempt"], "answers": [0, 1]})
    assert bad.status_code == 400


def test_attempts_are_signed_and_bound_to_their_course():
    attempt = client.post("/api/learn/course/sql/test", json={"chapter": 1}).json()
    answers = answers_for("sql", attempt["questions"], CHAPTER_QUESTIONS)
    payload, sig = attempt["attempt"].split(".")
    forged = sign("attempt", {"s": "sql", "k": "chapter", "m": 0, "q": [q["id"] for q in attempt["questions"]], "t": 0}).split(".")[0]
    assert client.post("/api/learn/course/sql/test/grade", json={"attempt": f"{forged}.{sig}", "answers": answers}).status_code == 400
    assert client.post("/api/learn/course/excel/test/grade", json={"attempt": attempt["attempt"], "answers": answers}).status_code == 400
    assert client.post("/api/learn/course/sql/test/grade", json={"attempt": "garbage", "answers": answers}).status_code == 400


def test_a_retake_asks_questions_the_learner_has_not_just_seen():
    first = client.post("/api/learn/course/sql/test", json={"chapter": 1}).json()
    seen = {q["id"] for q in first["questions"]}
    unseen = {q["id"] for q in learn.courses["sql"]["pool"] if q["module"] == 0} - seen
    retake = client.post("/api/learn/course/sql/test", json={"chapter": 1, "previous": first["attempt"]}).json()
    assert unseen and len(unseen & {q["id"] for q in retake["questions"]}) == min(len(unseen), CHAPTER_QUESTIONS)


def test_final_test_needs_every_chapter_and_passes_at_twenty_of_twenty_five():
    assert client.post("/api/learn/course/cybersecurity/test", json={}).status_code == 400
    tokens = chapter_tokens("cybersecurity")
    assert client.post("/api/learn/course/cybersecurity/test", json={"chapters": tokens[:-1]}).status_code == 400
    assert client.post("/api/learn/course/cybersecurity/test", json={"chapters": tokens[:-1] + chapter_tokens("sql")[:1]}).status_code == 400
    attempt, fail = take("cybersecurity", {"chapters": tokens}, right=FINAL_PASS - 1)
    assert attempt["total"] == FINAL_QUESTIONS and attempt["pass_mark"] == FINAL_PASS
    modules = {learn.questions["cybersecurity"][q["id"]]["module"] for q in attempt["questions"]}
    assert modules == set(range(len(learn.courses["cybersecurity"]["modules"]))), "the final test covers every chapter"
    assert not fail["passed"] and all("answer" not in r for r in fail["results"])
    _, ok = take("cybersecurity", {"chapters": tokens}, right=FINAL_PASS)
    assert ok["passed"] and ok["token"] and all("answer" in r for r in ok["results"]) and ok["review"] == []


def test_certificate_requires_a_final_pass_and_verifies():
    tokens = chapter_tokens("excel")
    assert client.post("/api/learn/course/excel/certificate", json={"token": tokens[0], "name": "Wei Jie"}).status_code == 400
    _, final = take("excel", {"chapters": tokens})
    assert client.post("/api/learn/course/sql/certificate", json={"token": final["token"], "name": "Wei Jie"}).status_code == 400
    cert = client.post("/api/learn/course/excel/certificate", json={"token": final["token"], "name": "  Tan   Wei Jie "}).json()["certificate"]
    assert cert["name"] == "Tan Wei Jie" and cert["score"] == cert["total"] == FINAL_QUESTIONS and cert["id"].startswith("PAI-")
    check = client.get(f"/api/certificates/verify/{cert['token']}").json()
    assert check["valid"] and check["certificate"]["course"] == learn.courses["excel"]["title"]
    assert check["certificate"]["hours"] > 1 and check["certificate"]["providers"]
    assert verify_certificate(tokens[0])["valid"] is False, "a chapter pass is not a certificate"


def test_tampered_or_garbage_certificates_are_rejected():
    cert = issue_certificate("sql", "Aisyah", 10, 10)
    payload, sig = cert["token"].split(".")
    forged = issue_certificate("sql", "Someone Else", 10, 10)["token"].split(".")[0] + "." + sig
    assert verify_certificate(forged)["valid"] is False
    assert verify_certificate(payload + ".AAAA")["valid"] is False
    assert verify_certificate("not-a-token")["valid"] is False
    assert verify_certificate("")["valid"] is False


@pytest.mark.parametrize("raw, expected", [("Nurul Ain", "Nurul Ain"), ("陈伟杰", "陈伟杰"), ("Kavitha\u0000 S", "Kavitha S")])
def test_names_are_cleaned(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "1", "12345", "x" * 61, "\u0007\u0008"])
def test_bad_names_are_rejected(raw):
    with pytest.raises(LearnError):
        clean_name(raw)


# ---------------------------------------------------------------- interface strings

@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to read the ES module")
def test_every_interface_key_is_translated():
    """A missing key renders as its raw name (e.g. 'nav_learn'), so every t("…") in the UI must exist in every language."""
    script = """
      import { STRINGS } from './static/i18n.js';
      console.log(JSON.stringify(Object.fromEntries(Object.entries(STRINGS).map(([k, v]) => [k, Object.keys(v)]))));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    tables = {lang: set(keys) for lang, keys in json.loads(out.stdout).items()}
    used = set()
    for js in (ROOT / "static").glob("*.js"):
        used |= set(re.findall(r'\bt\("([a-z0-9_]+)"', js.read_text(encoding="utf-8")))
    used |= {f"level_{c['level'].lower()}" for c in learn.courses.values()}
    for lang in ("en", "ms", "zh"):
        assert not used - tables[lang], (lang, sorted(used - tables[lang]))

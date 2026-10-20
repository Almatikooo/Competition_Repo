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
from app.learn import LEARN_DIR, PASS_RATIO, LearnError, clean_name, get_learn, issue_certificate, verify_certificate
from app.main import app

client = TestClient(app)
learn = get_learn()
catalog = get_catalog()
ROOT = Path(__file__).resolve().parents[1]
OPEN_LICENSES = {"MIT", "CC0 1.0", "CC BY 4.0", "CC BY-SA 4.0", "Open Government Licence v3.0", "Public domain (CC0)",
                 "Public domain (U.S. Government work)", "Design Science License"}


def key(sid):
    return [q["answer"] for q in learn.courses[sid]["quiz"]["questions"]]


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


def test_final_tests_are_grounded_and_balanced():
    positions = Counter()
    for sid, course in learn.courses.items():
        questions = course["quiz"]["questions"]
        assert 6 <= len(questions) <= 12, sid
        texts = {}
        for q in questions:
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
    assert course["title"] == "Databases and SQL" and course["syllabus"] and course["sources"]
    assert "quiz" not in course and "questions" not in json.dumps(course["syllabus"])
    quiz = client.get("/api/learn/course/sql/quiz").json()
    assert quiz["total"] == len(quiz["questions"]) >= 6
    assert all(set(q) == {"q", "options", "lesson", "lesson_title"} for q in quiz["questions"])
    assert client.get("/api/learn/course/nope").status_code == 404


def test_lesson_endpoint_serves_text_and_navigation():
    first = client.get("/api/learn/course/python/lesson/python-01").json()
    assert first["index"] == 1 and first["prev"] is None and first["next"] == "python-02"
    assert len(first["html"]) > 1000 and first["source"]["license"] == "CC BY 4.0"
    assert client.get("/api/learn/course/python/lesson/python-99").status_code == 404
    assert client.get("/api/learn/course/python/lesson/sql-01").status_code == 404


def test_courses_list_is_summarised():
    body = client.get("/api/learn/courses").json()
    assert len(body["courses"]) == len(catalog.skills) and body["pass_ratio"] == PASS_RATIO
    c = next(x for x in body["courses"] if x["skill"] == "excel")
    assert c["lessons"] >= 10 and c["minutes"] > 60 and c["provider"] and "html" not in c


def test_grading_thresholds_and_key_reveal():
    k = key("sql")
    n = len(k)
    pass_mark = learn.courses["sql"]["quiz"]["pass_mark"]
    wrong = [(a + 1) % len(q["options"]) for a, q in zip(k, learn.courses["sql"]["quiz"]["questions"])]
    fail = client.post("/api/learn/course/sql/grade", json={"answers": wrong}).json()
    assert not fail["passed"] and fail["score"] == 0 and fail["review"]
    assert all("answer" not in r for r in fail["results"]), "a failed attempt must not reveal the key"
    just = k[:pass_mark] + wrong[pass_mark:]
    assert client.post("/api/learn/course/sql/grade", json={"answers": just}).json()["passed"]
    below = k[:pass_mark - 1] + wrong[pass_mark - 1:]
    assert not client.post("/api/learn/course/sql/grade", json={"answers": below}).json()["passed"]
    full = client.post("/api/learn/course/sql/grade", json={"answers": k}).json()
    assert full["score"] == n and all("answer" in r for r in full["results"]) and full["review"] == []
    assert client.post("/api/learn/course/sql/grade", json={"answers": [0, 1]}).status_code == 400


def test_certificate_requires_a_pass_and_verifies():
    k = key("excel")
    assert client.post("/api/learn/course/excel/certificate", json={"answers": [None] * len(k), "name": "Wei Jie"}).status_code == 400
    cert = client.post("/api/learn/course/excel/certificate", json={"answers": k, "name": "  Tan   Wei Jie "}).json()["certificate"]
    assert cert["name"] == "Tan Wei Jie" and cert["score"] == len(k) and cert["id"].startswith("PAI-")
    check = client.get(f"/api/certificates/verify/{cert['token']}").json()
    assert check["valid"] and check["certificate"]["course"] == learn.courses["excel"]["title"]
    assert check["certificate"]["hours"] > 1 and check["certificate"]["providers"]


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

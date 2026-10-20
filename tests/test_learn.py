from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.catalog import get_catalog
from app.learn import LearnError, clean_name, get_learn, issue_certificate, verify_certificate
from app.main import app

client = TestClient(app)
learn = get_learn()
catalog = get_catalog()


def key(sid):
    return [q["answer"] for q in learn.courses[sid]["quiz"]]


def test_every_skill_has_a_valid_course():
    assert learn.validate() == []
    assert set(learn.courses) == set(catalog.skills)


def test_every_reading_is_attributed_and_openly_licensed():
    for sid, course in learn.courses.items():
        for lesson in course["lessons"]:
            e = learn.excerpts[lesson["wiki"]]
            assert e["license"] == "CC BY-SA 4.0" and e["license_url"].startswith("https://creativecommons.org/")
            assert "oldid=" in e["permalink"] and e["authors"] and e["retrieved"]
            assert 40 <= e["words"] <= 330, (sid, lesson["wiki"], e["words"])
            text = " ".join(b if isinstance(b, str) else " ".join(b["list"]) for b in e["text"])
            assert "displaystyle" not in text and "[]" not in text


def test_answer_positions_are_varied():
    # guards against an "always option A" quiz bank
    positions = Counter(q["answer"] for c in learn.courses.values() for q in c["quiz"])
    assert set(positions) == {0, 1, 2, 3}
    assert max(positions.values()) < 0.45 * sum(positions.values())


def test_course_endpoint_never_leaks_answers():
    body = client.get("/api/learn/course/sql").json()
    assert len(body["lessons"]) == 3 and len(body["quiz"]) == 5
    assert all("answer" not in q and "explain" not in q for q in body["quiz"])
    assert body["lessons"][0]["reading"]["license"] == "CC BY-SA 4.0"


def test_grading_thresholds_and_key_reveal():
    k = key("sql")
    wrong = [(a + 1) % 4 for a in k]
    fail = client.post("/api/learn/course/sql/grade", json={"answers": wrong}).json()
    assert not fail["passed"] and fail["score"] == 0
    assert all("answer" not in r for r in fail["results"]), "a failed attempt must not reveal the key"
    four = k[:4] + [wrong[4]]
    assert client.post("/api/learn/course/sql/grade", json={"answers": four}).json()["passed"]
    three = k[:3] + wrong[3:]
    assert not client.post("/api/learn/course/sql/grade", json={"answers": three}).json()["passed"]
    full = client.post("/api/learn/course/sql/grade", json={"answers": k}).json()
    assert full["score"] == 5 and all("explain" in r for r in full["results"])
    assert client.post("/api/learn/course/sql/grade", json={"answers": [0, 1]}).status_code == 400


def test_certificate_requires_a_pass_and_verifies():
    k = key("excel")
    assert client.post("/api/learn/course/excel/certificate", json={"answers": [None] * 5, "name": "Wei Jie"}).status_code == 400
    cert = client.post("/api/learn/course/excel/certificate", json={"answers": k, "name": "  Tan   Wei Jie "}).json()["certificate"]
    assert cert["name"] == "Tan Wei Jie" and cert["score"] == 5 and cert["id"].startswith("PAI-")
    check = client.get(f"/api/certificates/verify/{cert['token']}").json()
    assert check["valid"] and check["certificate"]["course"] == catalog.skills["excel"]["name"]["en"]


def test_tampered_or_garbage_certificates_are_rejected():
    cert = issue_certificate("sql", "Aisyah", 5, 5)
    payload, sig = cert["token"].split(".")
    forged = issue_certificate("sql", "Someone Else", 5, 5)["token"].split(".")[0] + "." + sig
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

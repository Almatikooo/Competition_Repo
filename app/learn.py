"""Learn: a full open course for every skill and verifiable Path.AI certificates.

Courses are assembled by scripts/learnkit from openly licensed curricula (MIT, CC0, CC BY, CC BY-SA, OGL, public
domain): every lesson is a real chapter, episode or guide, kept whole and re-typeset, with its source and licence
attached. data/learn/courses/<skill>.json describes a course; data/learn/lessons/<skill>/<lesson>.html holds the
sanitised lesson text.

The final test mixes questions from the source curricula's own open quiz banks with Path.AI questions whose answers
are quoted verbatim from a lesson (the build fails if a quote is not found). Grading happens on the server, so answer
keys never reach the browser before a learner passes. Certificates are stateless: the server signs (name, course,
score, date, nonce) with HMAC-SHA256, so anyone can verify a certificate link while no database of names is kept.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import math
import re
import secrets
import unicodedata
from functools import lru_cache

from . import config
from .catalog import get_catalog

LEARN_DIR = config.DATA / "learn"
PASS_RATIO = 0.7
MIN_QUESTIONS = 6
NAME_MIN, NAME_MAX = 2, 60
LESSON_ID = re.compile(r"^[a-z_]+-\d{2}$")


class LearnError(ValueError):
    pass


class LearnCatalog:
    def __init__(self) -> None:
        self.courses: dict[str, dict] = {}
        for path in sorted((LEARN_DIR / "courses").glob("*.json")):
            course = json.loads(path.read_text(encoding="utf-8"))
            if "skill" in course:  # v1 bundles (ai_data.json, …) are superseded by one file per course
                self.courses[course["skill"]] = course
        self.lesson_index: dict[str, dict[str, int]] = {
            sid: {lesson["id"]: i for i, lesson in enumerate(c["lessons"])} for sid, c in self.courses.items()}
        # Surfaced by the test suite; the app keeps serving the courses that are complete.
        self.problems = self.validate()

    # ------------------------------------------------------------ integrity

    def validate(self) -> list[str]:
        catalog = get_catalog()
        problems = []
        if missing := sorted(set(catalog.skills) - set(self.courses)):
            problems.append(f"no course for skills {missing}")
        for sid, course in self.courses.items():
            where = f"course {sid}"
            if sid not in catalog.skills:
                problems.append(f"{where}: unknown skill")
            for key in ("title", "subtitle", "outcomes", "modules", "lessons", "sources"):
                if not course.get(key):
                    problems.append(f"{where}: missing {key}")
            ids = [lesson["id"] for lesson in course.get("lessons", [])]
            if sorted(ids) != sorted(i for m in course.get("modules", []) for i in m["lessons"]):
                problems.append(f"{where}: modules and lessons disagree")
            source_ids = {s["id"] for s in course.get("sources", [])}
            for lesson in course.get("lessons", []):
                if not LESSON_ID.match(lesson["id"]) or not (LEARN_DIR / "lessons" / sid / f"{lesson['id']}.html").exists():
                    problems.append(f"{where}/{lesson['id']}: lesson text missing")
                if lesson.get("source") not in source_ids:
                    problems.append(f"{where}/{lesson['id']}: unattributed source {lesson.get('source')!r}")
            quiz = course.get("quiz", {})
            questions = quiz.get("questions", [])
            if len(questions) < MIN_QUESTIONS:
                problems.append(f"{where}: final test needs at least {MIN_QUESTIONS} questions (has {len(questions)})")
            if quiz.get("pass_mark") != math.ceil(PASS_RATIO * len(questions)):
                problems.append(f"{where}: pass mark must be {PASS_RATIO:.0%} of the questions")
            for i, q in enumerate(questions, start=1):
                opts = q.get("options", [])
                if not 2 <= len(opts) <= 5 or len(set(opts)) != len(opts) or not q.get("q"):
                    problems.append(f"{where} q{i}: needs a question and 2–5 distinct options")
                if not isinstance(q.get("answer"), int) or not 0 <= q["answer"] < len(opts):
                    problems.append(f"{where} q{i}: bad answer index")
                if q.get("lesson") not in self.lesson_index.get(sid, {}):
                    problems.append(f"{where} q{i}: points to an unknown lesson")
        return problems

    # ------------------------------------------------------------ views

    def _sources(self, sid: str) -> list[dict]:
        return self.courses[sid]["sources"]

    def summary(self, sid: str) -> dict:
        course = self.courses[sid]
        primary = next(s for s in course["sources"] if s["id"] == course["lessons"][0]["source"])
        return {"skill": sid, "title": course["title"], "subtitle": course["subtitle"], "level": course.get("level", "Beginner"),
                "lessons": len(course["lessons"]), "modules": len(course["modules"]), "minutes": course["minutes"],
                "questions": len(course["quiz"]["questions"]), "category": get_catalog().skills[sid]["category"],
                "provider": primary["name"], "providers": len(course["sources"]),
                "licenses": sorted({s["license"] for s in course["sources"]})}

    def detail(self, sid: str) -> dict:
        catalog = get_catalog()
        course = self.courses[sid]
        lessons = {lesson["id"]: lesson for lesson in course["lessons"]}
        modules = [{"title": m["title"], "minutes": sum(lessons[i]["minutes"] for i in m["lessons"]),
                    "lessons": [{"id": i, "title": lessons[i]["title"], "minutes": lessons[i]["minutes"], "source": lessons[i]["source"]}
                                for i in m["lessons"]]} for m in course["modules"]]
        skill = catalog.skills[sid]
        return {**self.summary(sid), "outcomes": course["outcomes"], "syllabus": modules, "sources": self._sources(sid),
                "pass_mark": course["quiz"]["pass_mark"], "practice": skill.get("practice"),
                "sdgs": [{"goal": catalog.goal_of(s["target"]), **s} for s in skill.get("sdgs", [])]}

    def lesson(self, sid: str, lid: str) -> dict:
        index = self.lesson_index[sid].get(lid)
        if index is None:
            raise KeyError(lid)
        course = self.courses[sid]
        lesson = course["lessons"][index]
        module = next(m["title"] for m in course["modules"] if lid in m["lessons"])
        source = next(s for s in course["sources"] if s["id"] == lesson["source"])
        nav = course["lessons"]
        return {"id": lid, "index": index + 1, "count": len(nav), "title": lesson["title"], "module": module,
                "minutes": lesson["minutes"], "words": lesson["words"], "toc": lesson["toc"], "html": lesson_html(sid, lid),
                "original_url": lesson["url"], "source": source,
                "prev": nav[index - 1]["id"] if index > 0 else None, "next": nav[index + 1]["id"] if index + 1 < len(nav) else None}

    def quiz(self, sid: str) -> dict:
        course = self.courses[sid]
        titles = {lesson["id"]: lesson["title"] for lesson in course["lessons"]}
        return {"pass_mark": course["quiz"]["pass_mark"], "total": len(course["quiz"]["questions"]),
                "questions": [{"q": q["q"], "options": q["options"], "lesson": q["lesson"], "lesson_title": titles[q["lesson"]]}
                              for q in course["quiz"]["questions"]]}

    def grade(self, sid: str, answers: list) -> dict:
        questions = self.courses[sid]["quiz"]["questions"]
        pass_mark = self.courses[sid]["quiz"]["pass_mark"]
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise LearnError(f"Send {len(questions)} answers.")
        correct = [isinstance(a, int) and a == q["answer"] for a, q in zip(answers, questions)]
        score = sum(correct)
        passed = score >= pass_mark
        results = []
        for ok, q in zip(correct, questions):
            item = {"correct": ok, "lesson": q["lesson"]}
            if passed:  # reveal the key only after a pass, so a retake still tests the learner
                item.update(answer=q["answer"], explain=q.get("explain") or "", evidence=q.get("evidence") or "")
            results.append(item)
        titles = {lesson["id"]: lesson["title"] for lesson in self.courses[sid]["lessons"]}
        review = [] if passed else sorted({q["lesson"] for ok, q in zip(correct, questions) if not ok}, key=self.lesson_index[sid].get)
        return {"score": score, "total": len(questions), "pass_mark": pass_mark, "passed": passed, "results": results,
                "review": [{"id": lid, "title": titles[lid]} for lid in review]}


@lru_cache(maxsize=None)
def lesson_html(sid: str, lid: str) -> str:
    return (LEARN_DIR / "lessons" / sid / f"{lid}.html").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def get_learn() -> LearnCatalog:
    return LearnCatalog()


# ---------------------------------------------------------------- certificates

def _secret() -> bytes:
    if config.CERT_SECRET:
        return config.CERT_SECRET.encode()
    path = config.CACHE_DIR / "cert_secret"
    if not path.exists():  # local development: generate once; set CERT_SECRET in production
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(payload_b64: str) -> bytes:
    return hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()[:16]


def clean_name(name: str) -> str:
    name = unicodedata.normalize("NFC", name or "")
    name = "".join(ch for ch in name if not unicodedata.category(ch).startswith("C"))
    name = " ".join(name.split())
    if not NAME_MIN <= len(name) <= NAME_MAX or not any(unicodedata.category(ch).startswith("L") for ch in name):
        raise LearnError(f"Please enter your name ({NAME_MIN}–{NAME_MAX} characters).")
    return name


def certificate_view(payload: dict, sig: bytes, token: str) -> dict:
    catalog = get_catalog()
    learn = get_learn()
    sid = payload["c"]
    course = learn.courses.get(sid, {})
    code = base64.b32encode(sig[:5]).decode()
    return {"id": f"PAI-{code[:4]}-{code[4:8]}", "name": payload["n"], "skill": sid,
            "course": course.get("title") or (catalog.skills[sid]["name"]["en"] if sid in catalog.skills else sid),
            "skill_name": catalog.skills[sid]["name"]["en"] if sid in catalog.skills else sid,
            "hours": round(course.get("minutes", 0) / 60, 1), "lessons": len(course.get("lessons", [])),
            "providers": [s["name"] for s in course.get("sources", [])],
            "score": payload["s"], "total": payload["t"], "date": payload["d"],
            "sdgs": sorted({catalog.goal_of(x["target"]) for x in catalog.skills.get(sid, {}).get("sdgs", [])}),
            "issuer": "Path.AI", "token": token}


def issue_certificate(sid: str, name: str, score: int, total: int) -> dict:
    payload = {"v": 1, "n": clean_name(name), "c": sid, "s": score, "t": total,
               "d": dt.datetime.now(dt.timezone.utc).date().isoformat(), "r": secrets.token_hex(4)}
    payload_b64 = _b64(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    sig = _signature(payload_b64)
    token = f"{payload_b64}.{_b64(sig)}"
    return certificate_view(payload, sig, token)


def verify_certificate(token: str) -> dict:
    try:
        payload_b64, sig_b64 = token.split(".")
        sig = _unb64(sig_b64)
        if not hmac.compare_digest(sig, _signature(payload_b64)):
            return {"valid": False, "reason": "signature does not match"}
        payload = json.loads(_unb64(payload_b64))
        if payload.get("v") != 1 or payload["c"] not in get_learn().courses:
            return {"valid": False, "reason": "unknown certificate format"}
        return {"valid": True, "certificate": certificate_view(payload, sig, token)}
    except (ValueError, KeyError, TypeError):
        return {"valid": False, "reason": "malformed certificate link"}

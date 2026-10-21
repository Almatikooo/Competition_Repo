"""Learn: a full open course for every skill and verifiable Path.AI certificates.

Courses are assembled by scripts/learnkit from openly licensed curricula (MIT, CC0, CC BY, CC BY-SA, OGL, public
domain): every lesson is a real chapter, episode or guide, kept whole and re-typeset, with its source and licence
attached. data/learn/courses/<skill>.json describes a course; data/learn/lessons/<skill>/<lesson>.html holds the
sanitised lesson text.

Every chapter ends with a short test that unlocks the next chapter, and the course ends with a final test that earns
the certificate. Each test is drawn at random from the course's question pool: questions from the source curricula's
own open quiz banks plus Path.AI questions whose answers are quoted verbatim from a lesson (the build fails if a quote
is not found), so a retake asks a different mix. Grading happens on the server and answer keys never reach the browser
before a learner passes the final test.

Nothing is stored on the server. A test attempt, a passed chapter and a passed final test are each an HMAC-signed
token the browser keeps: the final test is only handed out against signed passes for every chapter, and a
certificate only against a signed final pass. Certificates sign (name, course, score, date, nonce) the same way, so
anyone can verify a certificate link while no database of names is kept.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import math
import re
import secrets
import time
import unicodedata
from collections import Counter
from functools import lru_cache

from . import config
from .catalog import get_catalog

LEARN_DIR = config.DATA / "learn"
CHAPTER_QUESTIONS, CHAPTER_PASS = 5, 4   # the test after every chapter; passing it unlocks the next chapter
FINAL_QUESTIONS, FINAL_PASS = 25, 20     # the final test; passing it earns the certificate
MIN_CHAPTER_POOL = CHAPTER_QUESTIONS + 1  # spare questions, so a retake asks a different mix
MIN_COURSE_POOL = FINAL_QUESTIONS + 5
TEST_RULES = {"chapter": {"questions": CHAPTER_QUESTIONS, "pass": CHAPTER_PASS},
              "final": {"questions": FINAL_QUESTIONS, "pass": FINAL_PASS}}
_rng = secrets.SystemRandom()
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
        self.questions: dict[str, dict[str, dict]] = {sid: {q["id"]: q for q in c.get("pool", [])} for sid, c in self.courses.items()}
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
            pool = course.get("pool", [])
            module_of = {lid: i for i, m in enumerate(course.get("modules", [])) for lid in m["lessons"]}
            per_chapter = Counter(q.get("module") for q in pool)
            for i in range(len(course.get("modules", []))):
                if per_chapter[i] < MIN_CHAPTER_POOL:
                    problems.append(f"{where}: chapter {i + 1} needs at least {MIN_CHAPTER_POOL} questions (has {per_chapter[i]})")
            if len(pool) < MIN_COURSE_POOL:
                problems.append(f"{where}: needs at least {MIN_COURSE_POOL} questions for the final test (has {len(pool)})")
            if len({q.get("id") for q in pool}) != len(pool):
                problems.append(f"{where}: duplicate question ids")
            for q in pool:
                opts = q.get("options", [])
                tag = f"{where} q {q.get('id')}"
                if not 2 <= len(opts) <= 5 or len(set(opts)) != len(opts) or not q.get("q"):
                    problems.append(f"{tag}: needs a question and 2–5 distinct options")
                if not isinstance(q.get("answer"), int) or not 0 <= q["answer"] < len(opts):
                    problems.append(f"{tag}: bad answer index")
                if q.get("lesson") not in module_of or module_of[q["lesson"]] != q.get("module"):
                    problems.append(f"{tag}: points to an unknown lesson or the wrong chapter")
        return problems

    # ------------------------------------------------------------ views

    def _sources(self, sid: str) -> list[dict]:
        return self.courses[sid]["sources"]

    def summary(self, sid: str) -> dict:
        course = self.courses[sid]
        primary = next(s for s in course["sources"] if s["id"] == course["lessons"][0]["source"])
        return {"skill": sid, "title": course["title"], "subtitle": course["subtitle"], "level": course.get("level", "Beginner"),
                "lessons": len(course["lessons"]), "modules": len(course["modules"]), "minutes": course["minutes"],
                "chapters": len(course["modules"]), "category": get_catalog().skills[sid]["category"],
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
                "tests": TEST_RULES, "practice": skill.get("practice"),
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

    # ------------------------------------------------------------ tests

    def _draw(self, questions: list[dict], n: int, avoid: set[str]) -> list[dict]:
        """n questions at random, preferring ones the learner did not see in the previous attempt."""
        fresh = [q for q in questions if q["id"] not in avoid]
        seen = [q for q in questions if q["id"] in avoid]
        _rng.shuffle(fresh)
        _rng.shuffle(seen)
        return (fresh + seen)[:n]

    def _draw_final(self, sid: str, avoid: set[str]) -> list[dict]:
        """FINAL_QUESTIONS questions spread over the chapters in proportion to their share of the pool."""
        chapters = [[q for q in self.courses[sid]["pool"] if q["module"] == i] for i in range(len(self.courses[sid]["modules"]))]
        sizes = [len(c) for c in chapters]
        n = min(FINAL_QUESTIONS, sum(sizes))
        share = [n * size / sum(sizes) for size in sizes]
        quota = [min(size, int(x)) for size, x in zip(sizes, share)]
        while sum(quota) < n:  # largest remainder first, never more than a chapter has
            i = max((i for i in range(len(sizes)) if quota[i] < sizes[i]), key=lambda i: share[i] - quota[i])
            quota[i] += 1
        return [q for chapter, k in zip(chapters, quota) for q in self._draw(chapter, k, avoid)]

    def chapters_passed(self, sid: str, tokens: list) -> set[int]:
        passed = set()
        for token in tokens or []:
            data = unsign("chapter", token)
            if data and data.get("s") == sid and isinstance(data.get("m"), int):
                passed.add(data["m"])
        return passed & set(range(len(self.courses[sid]["modules"])))

    def start_test(self, sid: str, chapter: int | None = None, chapters: list | None = None, previous: str | None = None) -> dict:
        """A new attempt: chapter tests are open to everyone; the final test needs a signed pass for every chapter."""
        course = self.courses[sid]
        prev = unsign("attempt", previous) if previous else None
        avoid = set(prev["q"]) if prev and prev.get("s") == sid else set()
        if chapter is not None:
            if not 1 <= chapter <= len(course["modules"]):
                raise LearnError("Unknown chapter.")
            module = chapter - 1
            picked = self._draw([q for q in course["pool"] if q["module"] == module], CHAPTER_QUESTIONS, avoid)
            kind, rule = "chapter", (CHAPTER_QUESTIONS, CHAPTER_PASS)
        else:
            missing = sorted(set(range(len(course["modules"]))) - self.chapters_passed(sid, chapters))
            if missing:
                raise LearnError(f"Pass the chapter tests first (chapter {', '.join(str(m + 1) for m in missing)}).")
            module = None
            picked = self._draw_final(sid, avoid)
            kind, rule = "final", (FINAL_QUESTIONS, FINAL_PASS)
        if not picked:
            raise LearnError("This test has no questions yet.")
        order = self.lesson_index[sid]
        picked.sort(key=lambda q: order[q["lesson"]])
        titles = {lesson["id"]: lesson["title"] for lesson in course["lessons"]}
        attempt = sign("attempt", {"s": sid, "k": kind, "m": module, "q": [q["id"] for q in picked], "t": int(time.time())})
        return {"attempt": attempt, "kind": kind, "chapter": chapter, "chapter_title": course["modules"][module]["title"] if chapter else None,
                "total": len(picked), "pass_mark": pass_mark(len(picked), *rule),
                "questions": [{"id": q["id"], "q": q["q"], "options": q["options"], "lesson": q["lesson"], "lesson_title": titles[q["lesson"]]}
                              for q in picked]}

    def grade_test(self, sid: str, attempt: str, answers: list) -> dict:
        data = unsign("attempt", attempt)
        if not data or data.get("s") != sid or data.get("k") not in ("chapter", "final"):
            raise LearnError("This test attempt is not valid. Please start the test again.")
        questions = [self.questions[sid].get(qid) for qid in data["q"]]
        if None in questions:
            raise LearnError("This course was updated while you were taking the test. Please start it again.")
        if not isinstance(answers, list) or len(answers) != len(questions):
            raise LearnError(f"Send {len(questions)} answers.")
        final = data["k"] == "final"
        correct = [isinstance(a, int) and not isinstance(a, bool) and a == q["answer"] for a, q in zip(answers, questions)]
        score, total = sum(correct), len(questions)
        need = pass_mark(total, *((FINAL_QUESTIONS, FINAL_PASS) if final else (CHAPTER_QUESTIONS, CHAPTER_PASS)))
        passed = score >= need
        results = []
        for ok, q in zip(correct, questions):
            item = {"id": q["id"], "correct": ok, "lesson": q["lesson"]}
            if final and passed:  # the key is revealed only after the final test is passed, so every retake still tests
                item.update(answer=q["answer"], explain=q.get("explain") or "", evidence=q.get("evidence") or "")
            results.append(item)
        titles = {lesson["id"]: lesson["title"] for lesson in self.courses[sid]["lessons"]}
        review = [] if final and passed else sorted({q["lesson"] for ok, q in zip(correct, questions) if not ok}, key=self.lesson_index[sid].get)
        out = {"kind": data["k"], "chapter": None if final else data["m"] + 1, "score": score, "total": total, "pass_mark": need,
               "passed": passed, "results": results, "review": [{"id": lid, "title": titles[lid]} for lid in review]}
        if passed:
            now = int(time.time())
            out["token"] = (sign("final", {"s": sid, "sc": score, "n": total, "t": now}) if final
                            else sign("chapter", {"s": sid, "m": data["m"], "sc": score, "n": total, "t": now}))
        return out

    def certificate(self, sid: str, final_token: str, name: str) -> dict:
        data = unsign("final", final_token)
        if not data or data.get("s") != sid:
            raise LearnError("Pass the final test first.")
        return issue_certificate(sid, name, data["sc"], data["n"])


def pass_mark(total: int, questions: int, need: int) -> int:
    """The pass mark scaled to the test length (only differs from the rule while a course's question pool is short)."""
    return math.ceil(total * need / questions)


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


def _mac(purpose: str, payload_b64: str) -> bytes:
    # the purpose prefix keeps the token kinds apart: an attempt can never pass as a chapter pass or a certificate
    return hmac.new(_secret(), f"{purpose}:{payload_b64}".encode(), hashlib.sha256).digest()[:16]


def sign(purpose: str, payload: dict) -> str:
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_b64(_mac(purpose, payload_b64))}"


def unsign(purpose: str, token) -> dict | None:
    try:
        payload_b64, sig_b64 = str(token).split(".")
        if not hmac.compare_digest(_unb64(sig_b64), _mac(purpose, payload_b64)):
            return None
        data = json.loads(_unb64(payload_b64))
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError):
        return None


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

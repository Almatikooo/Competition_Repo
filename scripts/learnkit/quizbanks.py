"""Open quiz banks shipped with Microsoft's 'for Beginners' curricula (MIT). Each lesson has a post-lecture quiz;
we take questions from the post-lecture quizzes of the lessons a course includes."""
import json
from functools import lru_cache

from . import fetch as ft
from .courses import BANKS


@lru_cache(maxsize=None)
def _load_bank(key: str) -> dict[int, dict]:
    spec = BANKS[key]
    quizzes = {}
    for path in spec["files"]:
        data = json.loads(ft.gh_file(spec["repo"], path))
        for block in data if isinstance(data, list) else [data]:
            for quiz in block.get("quizzes", []):
                quizzes[int(quiz["id"])] = quiz
    return quizzes


def _truthy(value) -> bool:
    return value is True or str(value).strip().lower() == "true"


def bank_questions(lessons: list[dict], per_lesson: int = 2) -> list[dict]:
    picked = []
    for lesson in lessons:
        ref = lesson.get("_bank")
        if not ref:
            continue
        key, qid = ref
        quiz = _load_bank(key).get(int(qid))
        if not quiz:
            raise RuntimeError(f"quiz {qid} not found in bank {key} (lesson {lesson['id']})")
        if "post" not in quiz.get("title", "").lower():
            raise RuntimeError(f"quiz {qid} in bank {key} is not a post-lecture quiz: {quiz.get('title')!r}")
        candidates = []
        for item in quiz.get("quiz", []):
            options = [o["answerText"].strip() for o in item.get("answerOptions", [])]
            correct = [i for i, o in enumerate(item.get("answerOptions", [])) if _truthy(o.get("isCorrect"))]
            if len(options) < 2 or len(correct) != 1 or len(set(options)) != len(options) or not item.get("questionText", "").strip():
                continue
            candidates.append({"q": item["questionText"].strip(), "options": options, "answer": correct[0], "explain": "",
                               "lesson": lesson["id"], "origin": f"bank:{key}:{qid}", "source": BANKS[key]["source"]})
        candidates.sort(key=lambda c: -min(len(c["options"]), 3))  # prefer real multiple choice over true/false
        picked += candidates[:per_lesson]
    return picked

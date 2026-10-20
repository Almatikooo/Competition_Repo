"""Prints candidate evidence sentences per lesson, for writing grounded final-test questions:
    python -m scripts.learnkit.digest sql excel [--per 5]

Sentences come from exactly the text the build checks quotes against (plain_text + whitespace collapse), so a
sentence copied from this output into data/learn/quizzes/<skill>.json as "evidence" always verifies.
"""
import json
import re
import sys

from bs4 import BeautifulSoup

from . import convert as cv
from .build import OUT_COURSES, OUT_LESSONS

CUE = re.compile(r"\b(is|are|means|refers to|defined as|allows?|helps?|should|must|used to|includes?|consists? of|called|known as|"
                 r"because|so that|instead of|rather than|the first|the main|key|important|always|never|avoid|ensure)\b", re.I)
CODEY = re.compile(r"[{}<>;=]|\(\)|\[\]|\$|^\W|_\w+_|\w+\(\)")


def lesson_text(skill: str, lid: str) -> str:
    return re.sub(r"\s+", " ", cv.plain_text((OUT_LESSONS / skill / f"{lid}.html").read_text(encoding="utf-8")))


def candidates(skill: str, lid: str, per: int) -> list[str]:
    text = lesson_text(skill, lid)
    html = (OUT_LESSONS / skill / f"{lid}.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    # key points / objectives are the authors' own summaries: best quiz material
    boxed = [re.sub(r"\s+", " ", li.get_text(" ", strip=True)) for box in soup.select("div.box-keypoints, div.box-objectives") for li in box.find_all("li")]
    boxed = [b for b in boxed if 40 <= len(b) <= 240 and b in text]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", text)]
    scored = []
    for i, s in enumerate(sentences):
        if not 60 <= len(s) <= 240 or CODEY.search(s) or s.count(",") > 5 or s not in text:
            continue
        score = len(CUE.findall(s)) * 2 + (1 if 90 <= len(s) <= 180 else 0) - i / max(1, len(sentences))
        scored.append((score, i, s))
    best = [s for _, _, s in sorted(sorted(scored, reverse=True)[: per * 2], key=lambda x: x[1])][:per]
    seen, out = set(), []
    for s in boxed[:3] + best:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[: per + 2]


def main(argv: list[str]) -> None:
    per = 5
    if "--per" in argv:
        per = int(argv[argv.index("--per") + 1])
        argv = [a for i, a in enumerate(argv) if a != "--per" and (i == 0 or argv[i - 1] != "--per")]
    for skill in argv:
        course = json.loads((OUT_COURSES / f"{skill}.json").read_text(encoding="utf-8"))
        print(f"##### {skill} — {course['title']} ({len(course['lessons'])} lessons)")
        for n, lesson in enumerate(course["lessons"], start=1):
            print(f"[{n}] {lesson['title']}")
            for s in candidates(skill, lesson["id"], per):
                print(f"    - {s}")


if __name__ == "__main__":
    main(sys.argv[1:])

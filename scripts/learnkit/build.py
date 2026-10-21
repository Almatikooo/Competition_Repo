"""Builds Path.AI courses from open sources:  python -m scripts.learnkit.build [skill ...]

For every course in courses.COURSES this fetches each lesson, converts it to clean HTML (data/learn/lessons/<skill>/),
attaches the final quiz (open quiz-bank questions + our authored, evidence-checked questions) and writes
data/learn/courses/<skill>.json.
"""
import hashlib
import json
import math
import posixpath
import re
import sys

from bs4 import BeautifulSoup

from . import convert as cv
from . import fetch as ft
from .courses import BANKS, COURSES, REPO_BANK, SOURCES
from .quizbanks import bank_questions

ROOT = ft.ROOT
OUT_COURSES = ROOT / "data/learn/courses"
OUT_LESSONS = ROOT / "data/learn/lessons"
QUIZ_DIR = ROOT / "data/learn/quizzes"
WPM = 200          # reading speed used for lesson durations
MIN_WORDS = 150    # anything shorter is almost certainly a broken extraction


def first_heading(md: str) -> str | None:
    m = re.search(r"^#\s+(.+?)\s*#*\s*$", md, re.M)
    return re.sub(r"[*_`]|\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1)).strip() if m else None


def render_gh(spec: dict) -> dict:
    repo, path, flavor = spec["repo"], spec["path"], spec.get("flavor", "plain")
    meta, body = cv.split_front_matter(ft.gh_file(repo, path))
    title = spec.get("title") or (first_heading(body) if flavor == "docfx" else None) or meta.get("title") or first_heading(body) or posixpath.basename(path)
    title = re.sub(r"\s*\|\s*Microsoft (Docs|Learn).*$", "", str(title)).strip()
    directory = posixpath.dirname(path)
    if flavor == "carpentries":
        body = cv.carpentries(body)
    elif flavor == "mdx":
        body = cv.mdx(body, resolve_asset=lambda p: ft.gh_raw_url(repo, cv.rel_asset(directory, p)))
    elif flavor == "docfx":
        body = cv.docfx(body)
    elif flavor == "ph":
        body = cv.ph(body, posixpath.splitext(posixpath.basename(path))[0])
    for pattern in spec.get("cut", []):  # remove source-specific passages (regex over markdown)
        body = re.sub(pattern, "", body, flags=re.S | re.M)
    quiz_ids = [int(x) for x in re.findall(r"quiz/(\d+)", body)]
    html = cv.markdown_to_html(body)
    base_dir = directory + "/" if directory else ""
    html = cv.clean_html(html, page_url=ft.gh_blob_url(repo, base_dir or "README.md"), asset_base=ft.gh_raw_url(repo, base_dir),
                         link_base=ft.gh_blob_url(repo, base_dir), title=title, drop_headings=tuple(spec.get("drop_headings", ())))
    return {"title": str(title), "html": html, "url": ft.gh_blob_url(repo, path), "quiz_ids": quiz_ids}


def render_html(spec: dict) -> dict:
    url = spec["url"]
    raw = ft.get_text(url, browser=spec.get("browser", True))
    main = cv.select_main(raw, tuple(spec.get("select", ("main article", "article", "main", "body"))))
    if spec.get("latex"):
        main = cv.tex_to_html(main)
    title = spec.get("title")
    if not title:
        inner = BeautifulSoup(main, "lxml").find("h1")
        h1s = BeautifulSoup(raw, "lxml").find_all("h1")
        title = (inner or (h1s[-1] if h1s else None))
        title = title.get_text(" ", strip=True) if title else url
    html = cv.clean_html(main, page_url=url, title=title, drop_selectors=tuple(spec.get("drop", ())),
                         same_host_images=spec.get("same_host_images", True), keep_images=spec.get("images", True),
                         drop_headings=tuple(spec.get("drop_headings", ())))
    return {"title": title, "html": html, "url": url}


def render_govuk(spec: dict) -> dict:
    data = ft.govuk(spec["path"])
    details = data.get("details", {})
    body = details.get("body", "")
    if not body and details.get("parts"):  # a multi-page GOV.UK guide: its parts become the lesson's sections
        wanted = spec.get("guide_parts")
        body = "".join(f'<h2>{p["title"]}</h2>{p["body"]}' for p in details["parts"] if not wanted or p["slug"] in wanted)
    url = "https://www.gov.uk" + spec["path"]
    title = spec.get("title") or data.get("title")
    return {"title": title, "html": cv.clean_html(body, page_url=url, title=title, drop_headings=tuple(spec.get("drop_headings", ()))), "url": url}


def render_pressbooks(spec: dict) -> dict:
    ch = ft.pressbooks_chapter(spec["book"], spec["slug"])
    title = spec.get("title") or BeautifulSoup(ch["title"]["rendered"], "lxml").get_text(" ", strip=True)
    if spec.get("strip_number", True):
        title = re.sub(r"^(Chapter\s+)?\d+(\.\d+)*[.:]?\s+", "", title)
    html = cv.clean_html(ch["content"]["rendered"], page_url=ch["link"], title=title,
                         drop_selectors=(".media-attributions", ".footnotes", ".h5p-placeholder", ".interactive-content") + tuple(spec.get("drop", ())),
                         drop_headings=tuple(spec.get("drop_headings", ())))
    return {"title": title, "html": html, "url": ch["link"]}


def render_openstax(spec: dict) -> dict:
    url = f"https://openstax.org/books/{spec['book']}/pages/{spec['page']}"
    raw = ft.get_text(url, browser=True)
    main = cv.select_main(raw, ('div[data-type="page"]', "#main-content", "main"))
    soup = BeautifulSoup(raw, "lxml")
    head = soup.select_one('[data-type="document-title"]') or soup.find("h1")
    title = spec.get("title") or (head.get_text(" ", strip=True) if head else spec["page"])
    title = re.sub(r"^\d+(\.\d+)*\s+", "", title)
    html = cv.clean_html(main, page_url=url, title=title,
                         drop_selectors=('[data-type="document-title"]', ".os-teacher", ".os-eos", ".os-review-questions-container",
                                         ".os-critical-thinking-container", ".os-glossary-container", '[data-type="footnote-refs"]',
                                         ".concept-check", ".os-concept-check", '[data-type="abstract"] h3'),
                         drop_headings=("concept check", "key terms", "summary of learning outcomes") + tuple(spec.get("drop_headings", ())))
    return {"title": title, "html": html, "url": url}


RENDERERS = {"gh": render_gh, "html": render_html, "govuk": render_govuk, "pressbooks": render_pressbooks, "openstax": render_openstax}


def render(spec: dict) -> dict:
    if "parts" in spec:  # one lesson stitched from several short pages
        parts = [render(p) for p in spec["parts"]]
        html = "".join(f'<h2 id="{cv.heading_id(p["title"])}">{p["title"]}</h2>{cv.demote_headings(p["html"])}' for p in parts)
        quiz_ids = [q for p in parts for q in p.get("quiz_ids", [])]
        return {"title": spec["title"], "html": cv.sanitize(html), "url": parts[0]["url"], "quiz_ids": quiz_ids}
    return RENDERERS[spec["kind"]](spec)


AUTO_SPLIT_WORDS = 4500   # longer lessons are split at their own headings into ~AUTO_SPLIT_TARGET-word parts
AUTO_SPLIT_TARGET = 2400


def expand(spec: dict) -> list[dict]:
    """A spec yields one lesson, or several when a long page is split at its section headings."""
    res = render(spec)
    opts = spec.get("split")
    if not opts and spec.get("no_split") is not True and cv.word_count(res["html"]) > AUTO_SPLIT_WORDS:
        opts = {"target": AUTO_SPLIT_TARGET}
    if not opts:
        return [res]
    opts = opts if isinstance(opts, dict) else {}
    parts = cv.split_sections(res["html"], target=opts.get("target", 1600), drop=tuple(opts.get("drop", ())),
                              titles=opts.get("titles"), intro_title=opts.get("intro", res["title"]), keep=tuple(opts.get("pick", ())))
    if opts.get("take"):
        parts = [parts[i] for i in opts["take"] if i < len(parts)]
    if not parts:
        raise RuntimeError(f"splitting {res['url']} left no parts (pick/take too narrow?)")
    out = [{**res, "title": t, "html": cv.sanitize(h), "quiz_ids": [], "chapter": res["title"]} for t, h in parts]
    out[-1]["quiz_ids"] = res.get("quiz_ids", [])  # a curriculum's post-lesson quiz follows the end of the lesson
    out[-1]["_spec_bank"] = True
    return out


def lesson_bank_ref(spec: dict, res: dict):
    """(bank, quiz id) for lessons from curricula that ship an open quiz bank."""
    quiz = spec.get("quiz")
    if isinstance(quiz, (list, tuple)):
        return tuple(quiz)
    bank = REPO_BANK.get(spec.get("repo", ""))
    if quiz is not None and bank:
        return (bank, int(quiz))
    if bank and BANKS[bank].get("links_reliable") and res.get("quiz_ids"):
        return (bank, res["quiz_ids"][-1])
    return None


def build_course(skill: str, course: dict) -> dict:
    out_dir = OUT_LESSONS / skill
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.html"):
        old.unlink()
    modules, lessons, n = [], [], 0
    for module in course["modules"]:
        ids = []
        for spec in module["lessons"]:
            results = expand(spec)
            for res in results:
                n += 1
                lid = f"{skill}-{n:02d}"
                res["html"] = cv.finalize(res["html"])
                words = cv.word_count(res["html"])
                if words < MIN_WORDS:
                    raise RuntimeError(f"{lid} '{res['title']}' is suspiciously short ({words} words) — check the source {res['url']}")
                (out_dir / f"{lid}.html").write_text(res["html"], encoding="utf-8")
                title = spec.get("title") if len(results) == 1 and spec.get("title") else res["title"]
                title = re.sub(r"^[^\w‘'\"(]+", "", title).strip() or title  # drop decorative emoji
                title = re.sub(r"^(\d+\.(\d+\.?)*|\d+\.\d+(\.\d+)*)\s+", "", title) or title  # "3. Waste holders" -> "Waste holders"
                chapter = spec.get("title") or results[0].get("chapter") or results[0]["title"]
                if len(results) > 1 and res is results[0] and not (spec.get("split") or {}).get("titles"):
                    title = spec.get("title") or res.get("chapter") or title  # a split chapter's first part keeps the chapter title
                elif len(results) > 1 and len(title.split()) <= 2 and title != chapter and not (spec.get("split") or {}).get("titles"):
                    title = f"{chapter} · {title.strip('‘’')}"  # e.g. 'Challenge' alone says nothing in a syllabus
                bank = lesson_bank_ref(spec, res) if len(results) == 1 or res.get("_spec_bank") else None
                lessons.append({"id": lid, "title": title, "words": words, "minutes": max(3, math.ceil(words / WPM)),
                                "source": spec.get("source") or module.get("source") or course["source"], "url": res["url"],
                                "toc": cv.headings(res["html"])[:30], "_bank": bank})
                ids.append(lid)
                print(f"   {lid}  {words:5d}w  {title[:72]}")
        modules.append({"title": module["title"], "lessons": ids})
    pool = build_pool(skill, course, lessons, modules)
    used = sorted({l["source"] for l in lessons} | {q["source"] for q in pool["questions"] if q.get("source")})
    data = {k: course[k] for k in ("title", "subtitle", "level", "outcomes") if k in course}
    data.update(skill=skill, modules=modules, lessons=lessons, pool=pool["questions"], minutes=sum(l["minutes"] for l in lessons),
                sources=[{"id": s, **SOURCES[s]} for s in used])
    for lesson in data["lessons"]:
        lesson.pop("_bank", None)
    (OUT_COURSES / f"{skill}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


def authored_questions(skill: str, lessons: list[dict]) -> list[dict]:
    path = QUIZ_DIR / f"{skill}.json"
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding="utf-8"))["questions"]
    texts = {l["id"]: re.sub(r"\s+", " ", cv.plain_text((OUT_LESSONS / skill / f"{l['id']}.html").read_text())).lower() for l in lessons}
    by_number = {i + 1: l["id"] for i, l in enumerate(lessons)}
    out = []
    for item in items:
        lid = by_number.get(item["lesson"]) if isinstance(item["lesson"], int) else item["lesson"]
        evidence = re.sub(r"\s+", " ", item["evidence"]).strip().lower()
        if lid not in texts or evidence not in texts[lid]:
            raise RuntimeError(f"{skill}: evidence not found in lesson {item['lesson']} ({lid}): {item['evidence'][:90]!r}")
        if not (2 <= len(item["options"]) <= 5) or not (0 <= item["answer"] < len(item["options"])):
            raise RuntimeError(f"{skill}: malformed question {item['q'][:60]!r}")
        out.append({"q": item["q"], "options": item["options"], "answer": item["answer"], "explain": item.get("explain", ""),
                    "lesson": lid, "evidence": item["evidence"], "origin": "authored"})
    return out


POOL_PER_CHAPTER = 6    # a chapter test draws 5; one spare so a retake can differ
POOL_PER_COURSE = 30    # the final test draws 25, so retakes differ


def question_id(lesson_id: str, text: str) -> str:
    """Stable across rebuilds, so a test attempt in progress survives a content rebuild."""
    return hashlib.sha1(f"{lesson_id}|{text}".encode()).hexdigest()[:10]


def build_pool(skill: str, course: dict, lessons: list[dict], modules: list[dict]) -> dict:
    """Every question a course can ask: the open quiz banks of the source curricula plus our evidence-checked questions.
    Chapter tests draw from the questions of their chapter, the final test from the whole pool."""
    authored = authored_questions(skill, lessons)
    bank = bank_questions(lessons, per_lesson=None)
    module_of = {lid: i for i, m in enumerate(modules) for lid in m["lessons"]}
    order = {l["id"]: i for i, l in enumerate(lessons)}
    pool, seen = [], set()
    for q in sorted(authored + bank, key=lambda q: order[q["lesson"]]):
        qid = question_id(q["lesson"], q["q"])
        if qid in seen:
            continue
        seen.add(qid)
        pool.append({"id": qid, "module": module_of[q["lesson"]], **q})
    per_module = [sum(1 for q in pool if q["module"] == i) for i in range(len(modules))]
    short = [f"ch{i + 1}: {n}/{POOL_PER_CHAPTER}" for i, n in enumerate(per_module) if n < POOL_PER_CHAPTER]
    if len(pool) < POOL_PER_COURSE:
        short.append(f"course: {len(pool)}/{POOL_PER_COURSE}")
    return {"questions": pool, "per_module": per_module, "short": short}


def main(argv: list[str]) -> None:
    OUT_COURSES.mkdir(parents=True, exist_ok=True)
    wanted = argv or list(COURSES)
    failures = []
    for skill in wanted:
        print(f"== {skill}: {COURSES[skill]['title']}")
        try:
            data = build_course(skill, COURSES[skill])
        except Exception as exc:  # keep going so one broken source doesn't block the rest
            failures.append((skill, str(exc)))
            print(f"   !! FAILED: {exc}")
            continue
        per_module = [sum(1 for q in data["pool"] if q["module"] == i) for i in range(len(data["modules"]))]
        short = [f"ch{i + 1} {n}" for i, n in enumerate(per_module) if n < POOL_PER_CHAPTER]
        if len(data["pool"]) < POOL_PER_COURSE:
            short.append(f"course {len(data['pool'])}")
        print(f"   -> {len(data['lessons'])} lessons, {data['minutes']} min, pool {len(data['pool'])} q {per_module}"
              + (f"  NEEDS MORE: {', '.join(short)}" if short else ""))
    if failures:
        print("\nFAILURES:")
        for skill, err in failures:
            print(f"  {skill}: {err[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

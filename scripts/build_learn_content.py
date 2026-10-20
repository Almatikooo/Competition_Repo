"""Fetches the openly licensed reading for every Learn lesson and stores it with attribution.

Each lesson names a Wikipedia article ("wiki"). We store an excerpt of the article's lead section
(Wikipedia text is CC BY-SA 4.0), plus the permanent link to the exact revision used, so the demo
works offline and every excerpt can be attributed.

Usage:  python scripts/build_learn_content.py            # fetch missing excerpts
        python scripts/build_learn_content.py --refresh  # re-fetch all
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = ROOT / "data/learn/courses"
OUT = ROOT / "data/learn/excerpts.json"
API = "https://en.wikipedia.org/w/api.php"
UA = "PathAI-Hackathon/0.1 (https://github.com/Almatikooo/Competition_Repo; learning-content build)"
MAX_WORDS, MIN_WORDS, HARD_MAX = 230, 70, 320


def lesson_titles() -> list[str]:
    titles = []
    for path in sorted(COURSES_DIR.glob("*.json")):
        for course in json.loads(path.read_text(encoding="utf-8"))["courses"]:
            titles += [lesson["wiki"] for lesson in course["lessons"]]
    return sorted(set(titles))


def simplify_latex(latex: str) -> str:
    s = re.sub(r"\\mid\s*", "|", latex).replace("\\times", "×").replace("\\cdot", "·")
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    return " ".join(s.replace("{", "").replace("}", "").split())


def inline_math(text: str) -> str:
    """Plain-text extracts render a formula as indented lines followed by a {\\displaystyle ...} LaTeX
    fallback. Replace the whole block with a simplified one-line formula, e.g. p(y|x)."""
    while (j := text.find("{\\displaystyle")) >= 0:
        depth, k = 0, j
        while k < len(text):
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            if depth == 0:
                break
            k += 1
        latex = text[j + len("{\\displaystyle"):k]
        before = text[:j].split("\n")
        while len(before) > 1 and (not before[-1].strip() or before[-1].startswith(" ")):
            before.pop()
        after = re.sub(r"^\s*\n\s*", "", text[k + 1:])
        gap = " " if after[:1].isalnum() else ""
        text = "\n".join(before).rstrip() + " " + simplify_latex(latex) + gap + after
    return text


def clean(paragraph: str) -> str:
    p = re.sub(r"\(\s*[;,]?\s*\)", "", paragraph)  # empty brackets left by removed pronunciation audio
    p = re.sub(r"\(\s+[^()]{1,25}\)", "", p)  # leftover respellings such as "( LIN-uuks)"
    p = p.replace("[]", "").replace(" )", ")")  # empty citation brackets, stray spaces
    p = re.sub(r"\(\s*[;,]\s*", "(", p)
    p = re.sub(r"\s+([,.;:])", r"\1", p)
    return re.sub(r"\s{2,}", " ", p).strip()


def words(block) -> int:
    return sum(len(x.split()) for x in block["list"]) if isinstance(block, dict) else len(block.split())


def to_blocks(extract: str) -> list:
    """Plain-text lines -> paragraphs and bullet lists. Lines starting in lower case continue the previous
    sentence; short lines after a paragraph ending in ':' are list items."""
    blocks = []
    for line in (clean(x) for x in inline_math(extract).split("\n") if x.strip()):
        prev = blocks[-1] if blocks else None
        n = len(line.split())
        short = n <= 16
        if isinstance(prev, dict) and n <= 24:  # list items can be a little longer than a list opener
            prev["list"].append(line)
        elif isinstance(prev, str) and prev.endswith(":") and short:
            blocks.append({"list": [line]})
        elif isinstance(prev, str) and line[:1].islower():
            blocks[-1] = f"{prev} {line}"
        else:
            blocks.append(line)
    for b in blocks:
        if isinstance(b, dict):
            b["list"] = [re.sub(r"(,\s*(and|or)?|\s+(and|or)|[.;])$", "", item).strip() for item in b["list"]]
    return blocks


def excerpt(extract: str) -> tuple[list, bool]:
    units = []  # keep an introducing "...:" paragraph together with its list
    for b in to_blocks(extract):
        if isinstance(b, dict) and units and isinstance(units[-1][-1], str) and units[-1][-1].endswith(":"):
            units[-1].append(b)
        else:
            units.append([b])
    kept, total = [], 0
    for unit in units:
        n = sum(words(b) for b in unit)
        if not kept and n > MAX_WORDS and isinstance(unit[0], str) and len(unit) == 1:
            sentences = re.split(r"(?<=[.!?])\s+", unit[0])  # one very long first paragraph: cut at a sentence end
            cut = []
            for sentence in sentences:
                if cut and len(" ".join(cut + [sentence]).split()) > MAX_WORDS:
                    break
                cut.append(sentence)
            return [" ".join(cut)], True
        if kept and total + n > MAX_WORDS and (total >= MIN_WORDS or total + n > HARD_MAX):
            return kept, True
        kept += unit
        total += n
    return kept, False


def fetch(titles: list[str]) -> dict:
    out = {}
    with httpx.Client(headers={"User-Agent": UA}, timeout=30) as client:
        for start in range(0, len(titles), 20):
            batch = titles[start:start + 20]
            params = {"action": "query", "format": "json", "formatversion": 2, "redirects": 1,
                      "prop": "extracts|info|revisions|pageprops", "exintro": 1, "explaintext": 1, "exlimit": 20,
                      "inprop": "url", "rvprop": "ids|timestamp", "ppprop": "disambiguation", "titles": "|".join(batch)}
            data = client.get(API, params=params).raise_for_status().json()["query"]
            alias = {}
            for step in ("normalized", "redirects"):
                for item in data.get(step, []):
                    alias[item["from"]] = item["to"]
            pages = {p["title"]: p for p in data["pages"]}
            for title in batch:
                resolved = title
                while resolved in alias:
                    resolved = alias[resolved]
                page = pages.get(resolved)
                if not page or page.get("missing"):
                    out[title] = {"error": "missing"}
                    continue
                if "disambiguation" in (page.get("pageprops") or {}):
                    out[title] = {"error": "disambiguation"}
                    continue
                text, trimmed = excerpt(page.get("extract", ""))
                revid = page["revisions"][0]["revid"]
                out[title] = {
                    "source": "Wikipedia", "page_title": page["title"], "text": text,
                    "words": sum(words(b) for b in text), "trimmed": trimmed,
                    "url": page["fullurl"],
                    "permalink": f"https://en.wikipedia.org/w/index.php?title={quote(page['title'].replace(' ', '_'))}&oldid={revid}",
                    "revid": revid, "authors": "Wikipedia contributors",
                    "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    "retrieved": dt.date.today().isoformat(),
                }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    store = {} if args.refresh or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))
    titles = lesson_titles()
    todo = [t for t in titles if t not in store or "error" in store[t]]
    if todo:
        store.update(fetch(todo))
    store = {t: store[t] for t in titles}  # drop excerpts no lesson uses any more
    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    problems = {t: v["error"] for t, v in store.items() if "error" in v}
    short = {t: v["words"] for t, v in store.items() if "error" not in v and v["words"] < 50}
    print(f"{len(titles)} lessons · fetched {len(todo)} · problems {problems or 'none'} · short {short or 'none'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

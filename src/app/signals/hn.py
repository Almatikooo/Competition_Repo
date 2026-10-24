"""Job-market signal: monthly 'Ask HN: Who is hiring?' threads via the public HN Algolia API.

Each top-level comment in a thread is one job post. We count, per month, how many posts mention each
skill / role pattern. Only aggregate counts are stored in the repository; raw post text is cached
locally (data/cache, git-ignored) so that pattern changes can be re-counted without re-downloading.
"""
import asyncio
import html
import re

import httpx

from .store import HN_FILE, HN_RAW_DIR, now_iso, read_json, stable_hash, write_json

ALGOLIA = "https://hn.algolia.com/api/v1"
TITLE_RE = re.compile(r"Ask HN: Who is hiring\?\s*\((\w+)\s+(\d{4})\)", re.IGNORECASE)
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
TAG_RE = re.compile(r"<[^>]+>")


def clean_post(text: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", text)).split()).lower()


async def list_threads(client: httpx.AsyncClient, months: int) -> list[dict]:
    by_month: dict[str, dict] = {}
    page = 0
    while len(by_month) < months and page < 20:
        resp = await client.get(f"{ALGOLIA}/search_by_date",
                                params={"tags": "story,author_whoishiring", "hitsPerPage": 100, "page": page})
        resp.raise_for_status()
        data = resp.json()
        for hit in data["hits"]:
            match = TITLE_RE.search(hit.get("title") or "")
            if not match or match.group(1).lower() not in MONTHS:
                continue
            month = f"{int(match.group(2)):04d}-{MONTHS[match.group(1).lower()]:02d}"
            by_month.setdefault(month, {"id": int(hit["objectID"]), "month": month, "title": hit["title"]})
        if page >= data.get("nbPages", 1) - 1:
            break
        page += 1
    return sorted(by_month.values(), key=lambda t: t["month"])[-months:]


async def fetch_posts(client: httpx.AsyncClient, thread_id: int) -> list[str]:
    resp = await client.get(f"{ALGOLIA}/items/{thread_id}")
    resp.raise_for_status()
    return [clean_post(c["text"]) for c in resp.json().get("children", []) if c.get("text")]


def count_mentions(posts: list[str], patterns: dict[str, re.Pattern]) -> dict[str, int]:
    return {key: sum(1 for p in posts if pat.search(p)) for key, pat in patterns.items()}


async def refresh_hn(client: httpx.AsyncClient, catalog, months: int, log=print) -> dict:
    """Update data/signals/hn_monthly.json. Re-downloads only missing or still-growing months."""
    patterns_hash = stable_hash({"skills": {k: v.pattern for k, v in catalog.hn_skill_patterns.items()},
                                 "roles": {k: v.pattern for k, v in catalog.hn_role_patterns.items()}})
    store = read_json(HN_FILE, {"source": "hn_whoishiring", "months": {}})
    stale_patterns = store.get("patterns_hash") != patterns_hash
    threads = await list_threads(client, months)
    if not threads:
        raise RuntimeError("no 'Who is hiring?' threads found")
    recent = {t["month"] for t in threads[-2:]}  # threads keep receiving posts for a few weeks
    sem = asyncio.Semaphore(4)

    async def process(thread: dict) -> None:
        month = thread["month"]
        raw_file = HN_RAW_DIR / f"{month}.json"
        have_counts = month in store["months"] and not stale_patterns
        if have_counts and month not in recent:
            return
        posts = None if month in recent else read_json(raw_file, None)
        if posts is None:
            async with sem:
                posts = await fetch_posts(client, thread["id"])
            write_json(raw_file, posts)
            log(f"  HN {month}: downloaded {len(posts)} posts")
        store["months"][month] = {
            "thread_id": thread["id"],
            "title": thread["title"],
            "url": f"https://news.ycombinator.com/item?id={thread['id']}",
            "posts": len(posts),
            "skills": count_mentions(posts, catalog.hn_skill_patterns),
            "roles": count_mentions(posts, catalog.hn_role_patterns),
            "fetched_at": now_iso(),
        }

    await asyncio.gather(*(process(t) for t in threads))
    keep = {t["month"] for t in threads}
    store["months"] = {m: v for m, v in sorted(store["months"].items()) if m in keep}
    store["patterns_hash"] = patterns_hash
    store["refreshed_at"] = now_iso()
    write_json(HN_FILE, store)
    total = sum(v["posts"] for v in store["months"].values())
    return {"months": len(store["months"]), "first": min(store["months"]), "last": max(store["months"]), "posts": total}

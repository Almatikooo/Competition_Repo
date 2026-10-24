"""AI-advancement signal: research volume per AI-capability topic from the OpenAlex works index.

Counts are collected per half-year. Without an API key OpenAlex allows roughly 100 searches per day,
so we keep half-year buckets (13 queries x 5 buckets on first run, 13 x 2 on refresh) and cache every
bucket as soon as it is fetched. Set OPENALEX_API_KEY for a larger daily budget.
"""
import asyncio
import datetime as dt

import httpx

from ..config import OPENALEX_API_KEY, OPENALEX_MAILTO
from .store import OPENALEX_FILE, now_iso, read_json, write_json

API = "https://api.openalex.org/works"
REFETCH_RECENT = 2  # counts for recent buckets keep growing while OpenAlex indexes new works


class BudgetExceeded(RuntimeError):
    pass


def complete_halves(today: dt.date, n: int) -> list[tuple[str, str, str]]:
    """The last n complete half-years before `today`, oldest first: (label, start, end)."""
    year, half = (today.year, 1) if today.month >= 7 else (today.year - 1, 2)
    out = []
    for _ in range(n):
        start, end = (f"{year}-01-01", f"{year}-06-30") if half == 1 else (f"{year}-07-01", f"{year}-12-31")
        out.append((f"{year}H{half}", start, end))
        year, half = (year, 1) if half == 2 else (year - 1, 2)
    return list(reversed(out))


async def count_works(client: httpx.AsyncClient, query: str, start: str, end: str) -> int:
    params = {"search": query, "filter": f"from_publication_date:{start},to_publication_date:{end}",
              "per-page": 1, "select": "id"}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    resp = await client.get(API, params=params)
    if resp.status_code in (402, 403, 429):
        raise BudgetExceeded(f"OpenAlex returned {resp.status_code} (daily budget exhausted?)")
    resp.raise_for_status()
    return int(resp.json()["meta"]["count"])


async def refresh_openalex(client: httpx.AsyncClient, catalog, n_buckets: int = 5,
                           refetch_recent: int = REFETCH_RECENT, log=print) -> dict:
    topics = [catalog.capability_baseline] + catalog.capabilities
    store = read_json(OPENALEX_FILE, {"source": "openalex", "granularity": "half", "buckets": {}})
    # A changed query invalidates only that topic's counts, so editing one query stays within budget.
    old_queries = store.get("queries", {})
    for topic in topics:
        if old_queries.get(topic["id"]) != topic["query"]:
            for bucket in store["buckets"].values():
                bucket["counts"].pop(topic["id"], None)
    store["queries"] = {t["id"]: t["query"] for t in topics}
    buckets = complete_halves(dt.date.today(), n_buckets)
    recent = {b[0] for b in buckets[-refetch_recent:]} if refetch_recent else set()
    jobs = []
    for label, start, end in buckets:
        bucket = store["buckets"].setdefault(label, {"start": start, "end": end, "counts": {}})
        for topic in topics:
            if label in recent or topic["id"] not in bucket["counts"]:
                jobs.append((label, topic))
    sem = asyncio.Semaphore(3)
    exhausted: list[str] = []

    async def run(label: str, topic: dict) -> None:
        if exhausted:
            return
        bucket = store["buckets"][label]
        async with sem:
            try:
                bucket["counts"][topic["id"]] = await count_works(client, topic["query"], bucket["start"], bucket["end"])
                bucket["fetched_at"] = now_iso()
            except BudgetExceeded as exc:
                exhausted.append(str(exc))
            await asyncio.sleep(0.15)

    await asyncio.gather(*(run(label, topic) for label, topic in jobs))
    store.pop("queries_hash", None)
    store["refreshed_at"] = now_iso()
    write_json(OPENALEX_FILE, store)
    log(f"  OpenAlex: {len(jobs)} counts requested, buckets {[b[0] for b in buckets]}")
    if exhausted:
        raise BudgetExceeded(exhausted[0] + " — kept cached counts; set OPENALEX_API_KEY for a larger budget")
    return {"buckets": [b[0] for b in buckets], "requests": len(jobs)}

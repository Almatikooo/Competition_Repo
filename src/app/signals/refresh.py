"""Refresh all live trend sources.  Usage:  PYTHONPATH=src python -m app.signals.refresh [--skip-hn] [--skip-openalex]"""
import argparse
import asyncio

import httpx

from ..catalog import get_catalog
from ..config import HN_MONTHS
from .hn import refresh_hn
from .openalex import REFETCH_RECENT, refresh_openalex
from .store import META_FILE, now_iso, read_json, write_json

USER_AGENT = "PathAI/0.1 (SDC XMUM hackathon prototype; public trend research)"


async def refresh(hn: bool = True, openalex: bool = True, openalex_recent: int = REFETCH_RECENT, log=print) -> dict:
    catalog = get_catalog()
    meta = read_json(META_FILE, {})
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for name, enabled, job in (
            ("hn", hn, lambda: refresh_hn(client, catalog, HN_MONTHS, log)),
            ("openalex", openalex, lambda: refresh_openalex(client, catalog, refetch_recent=openalex_recent, log=log)),
        ):
            if not enabled:
                continue
            entry = meta.setdefault(name, {})
            entry["attempted_at"] = now_iso()
            try:
                log(f"Refreshing {name} ...")
                entry["result"] = await job()
                entry["status"] = "ok"
                entry["refreshed_at"] = entry["attempted_at"]
            except Exception as exc:  # keep the last good data; report the failure
                entry["status"] = f"error: {exc}"
                log(f"  {name} failed: {exc}")
    write_json(META_FILE, meta)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-hn", action="store_true")
    parser.add_argument("--skip-openalex", action="store_true")
    parser.add_argument("--openalex-recent", type=int, default=REFETCH_RECENT,
                        help="how many recent half-years to re-count (0 = only fetch missing counts)")
    args = parser.parse_args()
    meta = asyncio.run(refresh(hn=not args.skip_hn, openalex=not args.skip_openalex,
                               openalex_recent=args.openalex_recent))
    for name, entry in meta.items():
        print(f"{name}: {entry.get('status')} {entry.get('result', '')}")


if __name__ == "__main__":
    main()

"""Universities by country -> data/opportunities/universities.json

    python -m scripts.opportunities.universities

* Wikidata (CC0), via the public QLever SPARQL endpoint: every item that is a university (or a subclass of one),
  its country, official website and English name. Its number of Wikipedia sitelinks (language editions that have an
  article about it) is used as a rough, open measure of how widely known it is, to order the list.
* Hipo university-domains-list (MIT licence) fills in countries where Wikidata lists few institutions.

No rankings are reproduced (QS, THE and others are copyrighted); the page links to them instead.
"""
import datetime as dt
import json
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from . import fetch  # noqa: E402

OUT = ROOT / "data/opportunities/universities.json"
HIPO = "https://raw.githubusercontent.com/Hipo/university-domains-list/master/world_universities_and_domains.json"
QLEVER = "https://qlever.dev/api/wikidata"
PER_COUNTRY = 80
MIN_FROM_WIKIDATA = 15
HISTORICAL = {"DD", "YU", "SU", "CS", "ZR", "TP", "AN", "BU", "YD"}   # former countries (East Germany, Yugoslavia, ...)
QUERY = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?u ?code ?n ?site ?label ?end WHERE {
  ?u wdt:P31/wdt:P279* wd:Q3918 .
  ?u wdt:P17 ?country .
  ?country wdt:P297 ?code .
  ?u wikibase:sitelinks ?n .
  OPTIONAL { ?u wdt:P856 ?site }
  OPTIONAL { ?u rdfs:label ?label . FILTER(LANG(?label) = "en") }
  OPTIONAL { ?u wdt:P576 ?end }
}"""
SKIP_NAME = re.compile(r"\b(campus|faculty of|school of medicine|branch|centre for|center for|department of|library)\b", re.I)


def domain(url: str | None) -> str:
    if not url:
        return ""
    host = urllib.parse.urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def https(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def from_wikidata(client) -> dict[str, list[dict]]:
    data = fetch.get_json(client, f"{QLEVER}?{urllib.parse.urlencode({'query': QUERY})}", max_age_hours=24 * 30)
    items: dict[str, dict] = {}
    for row in data["results"]["bindings"]:
        qid = row["u"]["value"].rsplit("/", 1)[-1]
        if "end" in row or "label" not in row:
            continue                      # dissolved, or no English name
        item = items.setdefault(qid, {"qid": qid, "name": row["label"]["value"], "codes": set(), "sites": set(), "n": int(row["n"]["value"])})
        item["codes"].add(row["code"]["value"])
        if "site" in row:
            item["sites"].add(row["site"]["value"])
    by_country: dict[str, list[dict]] = defaultdict(list)
    for it in items.values():
        if SKIP_NAME.search(it["name"]) or re.fullmatch(r"Q\d+", it["name"]):
            continue
        site = sorted(it["sites"], key=lambda s: (not s.startswith("https"), len(s)))[0] if it["sites"] else None
        codes = set(it["codes"])
        for place, code in (("hong kong", "HK"), ("macau", "MO"), ("macao", "MO")):
            if place in it["name"].lower():
                codes = {code}          # Wikidata files Hong Kong and Macau institutions under China
        for code in codes:
            by_country[code].append({"name": it["name"], "site": https(site), "known": it["n"], "wikidata": it["qid"]})
    return by_country


def from_hipo(client) -> dict[str, list[dict]]:
    by_country: dict[str, list[dict]] = defaultdict(list)
    for u in fetch.get_json(client, HIPO, max_age_hours=24 * 30):
        site = https((u.get("web_pages") or [None])[0])
        by_country[u["alpha_two_code"]].append({"name": u["name"], "site": site, "known": 0, "wikidata": None})
    return by_country


def build() -> dict:
    with fetch.client() as client:
        wd = from_wikidata(client)
        hipo = from_hipo(client)
    countries = {}
    for code in sorted(set(wd) | set(hipo)):
        if not re.fullmatch(r"[A-Z]{2}", code) or code in HISTORICAL:
            continue
        items = sorted(wd.get(code, []), key=lambda x: (-x["known"], x["name"]))
        seen_names = {x["name"].lower() for x in items}
        seen_domains = {domain(x["site"]) for x in items if x["site"]}
        if len(items) < MIN_FROM_WIKIDATA:
            for x in sorted(hipo.get(code, []), key=lambda x: x["name"]):
                if x["name"].lower() in seen_names or (x["site"] and domain(x["site"]) in seen_domains):
                    continue
                items.append(x)
                seen_names.add(x["name"].lower())
        total = max(len(items), len(hipo.get(code, [])))
        countries[code] = {"total": total, "items": items[:PER_COUNTRY]}
    data = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "countries": countries,
            "sources": [{"name": "Wikidata", "url": "https://www.wikidata.org/", "license": "CC0 1.0"},
                        {"name": "Hipo university-domains-list", "url": "https://github.com/Hipo/university-domains-list", "license": "MIT"}]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def main() -> None:
    data = build()
    c = data["countries"]
    print(f"{len(c)} countries · {sum(len(v['items']) for v in c.values())} universities listed · {sum(v['total'] for v in c.values())} known")
    for code in ["MY", "SG", "GB", "US", "DE", "AU", "CN", "JP", "KZ"]:
        if code in c:
            print(code, c[code]["total"], [x["name"] for x in c[code]["items"][:5]])
    print(f"size: {OUT.stat().st_size / 1e6:.2f} MB", Counter(len(v["items"]) >= 10 for v in c.values()))


if __name__ == "__main__":
    main()

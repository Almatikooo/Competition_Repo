"""Open job postings worldwide -> data/opportunities/jobs.json

    python -m scripts.opportunities.jobs
    python -m scripts.opportunities.jobs --texts-only   # only re-write the trimmed texts for the current snapshot (offline)

Sources (all public and read-only; every listing links back to the original posting):
  * company job boards on Greenhouse, Lever and Ashby (their public embed APIs), listed in data/opportunities/sources.json
  * Hacker News "Ask HN: Who is hiring?" (latest monthly thread, via the HN Algolia API)
  * remote-job boards with open APIs: Himalayas, Jobicy, Remotive (credited and linked as their terms ask)
  * Arbeitnow (jobs in Germany)

For each posting we keep only facts needed to match and link it: title, company, where it can be done, level,
the Path.AI roles its title matches and the catalogue skills its text asks for. Descriptions are not stored in the
snapshot: only a trimmed copy (requirement sentences, see trim.py) goes to the git-ignored cache, for the language model
to read once (scripts/opportunities/enrich.py).
"""
import datetime as dt
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.catalog import alias_regex, get_catalog  # noqa: E402

from . import fetch  # noqa: E402
from .places import countries_in, remote_scope  # noqa: E402
from .trim import text_hash, trim, url_key  # noqa: E402

OUT = ROOT / "data/opportunities/jobs.json"
TEXTS = ROOT / "data/cache/opportunities/texts.jsonl"     # trimmed posting texts for enrich.py (cache only, not in git)
SOURCES = json.loads((ROOT / "data/opportunities/sources.json").read_text(encoding="utf-8"))
DEFAULT_CAP = 400
MAX_AGE_DAYS = 120

TAG = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"Ask HN: Who is hiring\?\s*\((\w+)\s+(\d{4})\)", re.I)
INTERN = re.compile(r"\bintern(ship)?s?\b|\btrainee\b|\bapprentice|\bworking student\b|\bwerkstudent|\bpraktik", re.I)
ENTRY = re.compile(r"\b(junior|jr\.?|graduate|entry[- ]level|new grad|fresh grad|early career|associate|accelerator program)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|head of|director|vp|vice president|chief|distinguished|architect)\b", re.I)

# Job titles for roles whose catalogue entry has no Hacker News pattern, and for the "current" roles people hold today.
EXTRA_TITLES = {
    "renewable_energy_engineer": r"renewable|solar engineer|wind (turbine )?engineer|energy systems engineer|power systems engineer|grid engineer",
    "solar_pv_technician": r"solar (pv )?(installer|technician)|pv (installer|technician)|photovoltaic",
    "energy_manager": r"energy (manager|auditor|analyst|engineer|efficiency)",
    "esg_analyst": r"\besg\b|sustainability (analyst|manager|specialist|lead|associate)|climate (analyst|specialist)|carbon (analyst|accounting)",
    "ev_technician": r"\bev (technician|engineer)|electric vehicle|battery (technician|engineer)|charging (technician|engineer)",
    "precision_agri_technologist": r"agronom|precision agri|agtech|agricultur",
    "ld_specialist": r"learning (and|&) development|instructional designer|training (specialist|manager|coordinator)|enablement (specialist|manager)",
    "financial_analyst": r"financial analyst|\bfp ?& ?a\b|finance analyst|financial planning",
    "data_entry_clerk": r"data entry|data clerk",
    "accounting_clerk": r"bookkeep|accounts (payable|receivable)|accounting (clerk|assistant|specialist|associate)|\baccountant\b|billing specialist|reconcil",
    "customer_service_rep": r"customer (service|support|experience) (representative|agent|specialist|associate|advocate|advisor)|support (agent|specialist)|customer care|call cent",
    "graphic_designer": r"graphic designer|visual designer|brand designer|motion designer|illustrator",
    "admin_assistant": r"administrative assistant|admin assistant|executive assistant|office (manager|administrator|coordinator)",
    "cashier": r"\bcashier",
    "bank_teller": r"bank teller|\bteller\b",
    "retail_sales": r"retail (sales|associate|assistant)|sales associate|store (associate|assistant)",
    "teacher": r"\bteacher\b|\btutor\b|\blecturer\b|\beducator\b",
    "electrician": r"electrician|electrical technician",
    "nurse": r"\bnurse\b|\bnursing\b",
    "supply_chain_analyst": r"supply chain|logistics (analyst|coordinator|specialist|executive|manager|planner)|demand planner|procurement (specialist|analyst|executive|manager)|purchasing (officer|executive|specialist)|\bbuyer\b",
    "quality_engineer": r"quality (engineer|manager|control|lead)|process (improvement|excellence) (engineer|manager|specialist|lead)|continuous improvement|six sigma|lean (manager|specialist|engineer)|manufacturing engineer|industrial engineer",
    "environmental_engineer": r"environmental (engineer|scientist|specialist|officer|consultant)|waste management|water (treatment|engineer)",
    "drone_technician": r"\bdrone|\buav\b|remote sensing|gis (technician|specialist|analyst)|geospatial (analyst|technician)",
    "care_coordinator": r"care coordinator|community health|patient (navigator|coordinator|advocate)|health coach|caregiver|care (assistant|worker)",
    "factory_operator": r"production (operator|associate|worker|technician)|machine operator|assembl(y|er) (operator|technician|worker)|line operator|manufacturing (operator|associate|technician)",
    "warehouse_clerk": r"warehouse|inventory (clerk|associate|specialist|controller)|stock (clerk|controller|associate)|storekeeper",
    "delivery_driver": r"delivery (driver|rider|associate)|\bcourier\b|\bdriver\b|dispatch rider",
    "telemarketer": r"telemarket|telesales|inside sales (representative|agent)",
    "receptionist": r"receptionist|front desk|front office",
    "copywriter": r"copywriter|content writer|blog writer",
    "translator": r"translator|interpreter|locali[sz]ation (specialist|manager|coordinator)",
    "claims_examiner": r"claims (adjuster|examiner|handler|specialist|analyst|investigator|processor)",
    "hr_assistant": r"hr (assistant|administrator|coordinator)|payroll (assistant|specialist|administrator|officer)|people (operations )?coordinator",
}


def plain(text: str | None) -> str:
    text = html.unescape(html.unescape(text or ""))
    return " ".join(TAG.sub(" ", text).split())


def day(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            v = float(value)
            return dt.datetime.fromtimestamp(v / 1000 if v > 1e12 else v, dt.timezone.utc).date().isoformat()
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def level_of(title: str) -> str:
    if INTERN.search(title):
        return "intern"
    if SENIOR.search(title):
        return "senior"
    if ENTRY.search(title):
        return "entry"
    return "mid"


# Aliases that work on a CV but mislead on a job ad (benefits sections promise "training", "medical cover", "mentoring",
# "networking events"); soft skills that nearly every ad mentions are left to the role profile.
JOB_ALIAS_DROP = {"teaching_training": {"training"}, "healthcare_basics": {"medical", "healthcare"}, "linux_networking": {"networking"},
                  "leadership": {"coaching", "mentoring"}, "creative_thinking": {"creative"}, "data_entry": {"typing"}}
JOB_SKIP = {"lifelong_learning"}


def trigger(alias: str) -> str | None:
    """A piece of plain text that `alias` cannot match without (lower-case), so a fast substring test can skip the
    regex; None when the alias is too irregular to tell (then the regex always runs)."""
    alias = alias.lower()
    alias = re.sub(r"\(\?<?[!=][^)]*\)", "\0", alias)        # look-arounds are not text the match contains
    alias = alias.replace("(?:", "(")
    if re.search(r"[|\[\]{}]", alias) or re.search(r"\)[?*]", alias):
        return None
    alias = re.sub(r"\\.[?*]|.[?*]", "\0", alias)            # an optional character splits the text
    pieces = re.split(r"\\[bBdDsSwW]|\\.|[\0^$.+()]", alias)
    best = max(pieces, key=len, default="")
    return best if len(best) >= 3 else None


class Matcher:
    def __init__(self) -> None:
        catalog = get_catalog()
        self.skills = {}
        for sid, s in catalog.skills.items():
            if sid in JOB_SKIP:
                continue
            aliases = [a for a in s["aliases"] if a.lower() not in JOB_ALIAS_DROP.get(sid, set())]
            triggers = [trigger(a) for a in aliases]
            self.skills[sid] = (None if None in triggers else triggers,
                                [re.compile("|".join(f"(?:{alias_regex(a).pattern})" for a in aliases), re.I)])
        self.titles = {rid: p for rid, p in catalog.hn_role_patterns.items()}
        for rid, pattern in EXTRA_TITLES.items():
            if rid in catalog.roles and rid not in self.titles:
                self.titles[rid] = re.compile(pattern, re.I)

    def roles(self, title: str) -> list[str]:
        hits = [(len(m.group(0)), rid) for rid, p in self.titles.items() if (m := p.search(title))]
        return [rid for _, rid in sorted(hits, reverse=True)]

    def skills_in(self, text: str) -> list[str]:
        text = text[:12000]
        lower = text.lower()
        return [sid for sid, (triggers, patterns) in self.skills.items()
                if (triggers is None or any(t in lower for t in triggers)) and any(p.search(text) for p in patterns)]


def record(m: Matcher, *, source, company, title, url, posted, location, text, remote_hint="", kind=None,
           countries=None, scope=None) -> dict | None:
    title = " ".join((title or "").split())
    if not title or not url:
        return None
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]   # a few company boards still list http links; all serve https
    loc_text = " · ".join(x for x in [location, remote_hint] if x)
    places = countries if countries is not None else countries_in(location or "")
    remote = scope if scope is not None else remote_scope(loc_text)
    if remote == "UNSPECIFIED" and places:
        remote = list(places)                # "Remote" at a company with listed countries: remote within those
    roles = m.roles(title)
    skills = m.skills_in(f"{title}. {text}")
    return {"title": title[:140], "company": (company or "").strip()[:80], "url": url, "source": source, "posted": day(posted),
            "location": (location or "")[:90], "countries": places, "remote": remote, "level": level_of(title),
            "type": kind, "roles": roles, "skills": skills, "text": text}


# ---------------------------------------------------------------- company boards

def greenhouse(m: Matcher, client, board: dict) -> list[dict]:
    data = fetch.get_json(client, f"https://boards-api.greenhouse.io/v1/boards/{board['slug']}/jobs?content=true")
    out = []
    for j in data.get("jobs", []):
        location = (j.get("location") or {}).get("name", "")
        offices = ", ".join(o.get("location") or o.get("name") or "" for o in j.get("offices") or [])
        places = countries_in(location) or countries_in(offices)
        out.append(record(m, source=f"greenhouse:{board['slug']}", company=board["company"], title=j.get("title"), url=j.get("absolute_url"),
                          posted=j.get("first_published") or j.get("updated_at"), location=location, text=plain(j.get("content")),
                          countries=places))
    return out


def lever(m: Matcher, client, board: dict) -> list[dict]:
    data = fetch.get_json(client, f"https://api.lever.co/v0/postings/{board['slug']}?mode=json")
    out = []
    for j in data if isinstance(data, list) else []:
        cats = j.get("categories") or {}
        locations = cats.get("allLocations") or [cats.get("location") or ""]
        location = " / ".join(x for x in locations if x)
        places = countries_in(location)
        if j.get("country") and j["country"] not in places:
            places = [j["country"]] + places
        lists = " ".join(f"{x.get('text', '')} {plain(x.get('content'))}" for x in j.get("lists") or [])
        hint = "remote" if (j.get("workplaceType") == "remote") else ""
        out.append(record(m, source=f"lever:{board['slug']}", company=board["company"], title=j.get("text"), url=j.get("hostedUrl"),
                          posted=j.get("createdAt"), location=location, text=f"{j.get('descriptionPlain', '')} {lists} {j.get('additionalPlain', '')}",
                          remote_hint=hint + (f" {location}" if hint else ""), kind=(cats.get("commitment") or None), countries=places))
    return out


def ashby(m: Matcher, client, board: dict) -> list[dict]:
    data = fetch.get_json(client, f"https://api.ashbyhq.com/posting-api/job-board/{board['slug']}")
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        names = [j.get("location") or ""] + [s.get("location") or "" for s in j.get("secondaryLocations") or []]
        location = " / ".join(dict.fromkeys(x for x in names if x))
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
        places = countries_in(f"{location}, {country}")
        hint = "remote" if j.get("isRemote") or j.get("workplaceType") == "Remote" else ""
        out.append(record(m, source=f"ashby:{board['slug']}", company=board["company"], title=j.get("title"), url=j.get("jobUrl"),
                          posted=j.get("publishedAt"), location=location, text=j.get("descriptionPlain") or plain(j.get("descriptionHtml")),
                          remote_hint=hint + (f" {location} {country}" if hint else ""), kind=j.get("employmentType"), countries=places))
    return out


BOARDS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


# ---------------------------------------------------------------- feeds

def hacker_news(m: Matcher, client, threads: int = 3) -> list[dict]:
    """The latest monthly threads (older posts are dropped by the 120-day cut-off in build())."""
    hits = fetch.get_json(client, "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=40")["hits"]
    out = []
    for thread in [h for h in hits if TITLE_RE.search(h.get("title") or "")][:threads]:
        out += hn_thread(m, client, thread)
    return out


def hn_thread(m: Matcher, client, thread: dict) -> list[dict]:
    item = fetch.get_json(client, f"https://hn.algolia.com/api/v1/items/{thread['objectID']}")
    out = []
    for c in item.get("children", []):
        raw = c.get("text") or ""
        first = html.unescape(TAG.sub(" ", raw.split("<p>")[0]))
        parts = [p.strip() for p in first.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        company = re.sub(r"\(.*?\)", "", parts[0]).strip()
        candidates = [p for p in parts[1:] if not re.search(r"https?://|www\.|\.(com|io|ai|co|org|dev)\b|@", p, re.I)]
        if not candidates:
            continue
        title = next((p for p in candidates if m.roles(p) or re.search(r"engineer|developer|designer|analyst|scientist|manager|lead|"
                                                                        r"specialist|architect|marketer|writer|recruiter", p, re.I)), candidates[0])
        location = " | ".join(p for p in parts[1:] if p != title and (countries_in(p) or re.search(r"remote|onsite|on-site|hybrid", p, re.I)))
        rec = record(m, source="hn", company=company, title=title[:140], url=f"https://news.ycombinator.com/item?id={c['id']}",
                     posted=c.get("created_at"), location=location, text=plain(raw))
        if rec:
            out.append(rec)
    return out


def himalayas(m: Matcher, client, pages: int) -> list[dict]:
    out, cursor = [], None
    for _ in range(pages):
        url = "https://himalayas.app/jobs/api?limit=20" + (f"&cursor={cursor}" if cursor else "")
        data = fetch.get_json(client, url, pause=1.0)
        for j in data.get("jobs", []):
            allowed = j.get("locationRestrictions") or []
            scope = [c for name in allowed for c in countries_in(name)] or "WORLD"
            out.append(record(m, source="himalayas", company=j.get("companyName"), title=j.get("title"), url=j.get("applicationLink") or j.get("guid"),
                              posted=j.get("pubDate"), location="Remote · " + (", ".join(allowed) if allowed else "Worldwide"),
                              text=plain(j.get("description") or j.get("excerpt")), kind=j.get("employmentType"), countries=[], scope=scope))
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return out


def jobicy(m: Matcher, client, pages: int) -> list[dict]:
    out, cursor = [], None
    for _ in range(pages):
        url = "https://jobicy.com/api/v2/remote-jobs?count=50" + (f"&cursor={cursor}" if cursor else "")
        data = fetch.get_json(client, url, pause=1.0)
        for j in data.get("jobs", []):
            geo = j.get("jobGeo") or "Anywhere"
            scope = remote_scope(f"remote {geo}")
            out.append(record(m, source="jobicy", company=j.get("companyName"), title=html.unescape(j.get("jobTitle") or ""), url=j.get("url"),
                              posted=j.get("pubDate"), location=f"Remote · {geo}", text=plain(j.get("jobDescription") or j.get("jobExcerpt")),
                              kind=", ".join(j.get("jobType") or []) or None, countries=[], scope=scope))
        cursor = data.get("nextCursor")
        if not cursor or str(data.get("hasMore")).lower() != "true":
            break
    return out


def remotive(m: Matcher, client) -> list[dict]:
    data = fetch.get_json(client, "https://remotive.com/api/remote-jobs", max_age_hours=12)
    out = []
    for j in data.get("jobs", []):
        where = j.get("candidate_required_location") or "Worldwide"
        out.append(record(m, source="remotive", company=j.get("company_name"), title=j.get("title"), url=j.get("url"), posted=j.get("publication_date"),
                          location=f"Remote · {where}", text=plain(j.get("description")), kind=j.get("job_type"), countries=[],
                          scope=remote_scope(f"remote {where}")))
    return out


def remote_ok(m: Matcher, client) -> list[dict]:
    """Remote OK's API terms: link back to the job's Remote OK page and name Remote OK as the source (the job cards do both)."""
    data = fetch.get_json(client, "https://remoteok.com/api", max_age_hours=20)
    out = []
    for j in data[1:]:  # the first item is the API's legal notice
        if not isinstance(j, dict) or not j.get("position") or not j.get("url"):
            continue
        where = (j.get("location") or "").strip()
        out.append(record(m, source="remoteok", company=j.get("company"), title=j.get("position"), url=j.get("url"), posted=j.get("date"),
                          location=f"Remote · {where or 'Worldwide'}", text=f"{plain(j.get('description'))} {' '.join(j.get('tags') or [])}",
                          countries=[], scope=remote_scope(f"remote {where}") if where else "WORLD"))
    return out


def arbeitnow(m: Matcher, client, pages: int) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        data = fetch.get_json(client, f"https://www.arbeitnow.com/api/job-board-api?page={page}", pause=1.0)
        for j in data.get("data", []):
            location = j.get("location") or ""
            places = countries_in(location) or ["DE"]
            out.append(record(m, source="arbeitnow", company=j.get("company_name"), title=j.get("title"), url=j.get("url"),
                              posted=j.get("created_at"), location=location, text=plain(j.get("description")),
                              remote_hint="remote" if j.get("remote") else "", countries=places))
        if not data.get("links", {}).get("next"):
            break
    return out


# ---------------------------------------------------------------- build

def build() -> dict:
    m = Matcher()
    feeds = SOURCES["feeds"]
    jobs: list[dict] = []
    stats: dict[str, int] = {}
    with fetch.client() as client:
        for board in SOURCES["boards"]:
            try:
                got = [r for r in BOARDS[board["ats"]](m, client, board) if r]
            except Exception as exc:  # one broken board must not stop the build
                print(f"  !! {board['company']}: {exc}")
                continue
            got.sort(key=lambda r: r["posted"] or "", reverse=True)
            got = got[: board.get("cap", DEFAULT_CAP)]
            stats[board["company"]] = len(got)
            jobs += got
        for key, run in (("hn", lambda: hacker_news(m, client)), ("himalayas", lambda: himalayas(m, client, feeds["himalayas"]["pages"])),
                         ("jobicy", lambda: jobicy(m, client, feeds["jobicy"]["pages"])), ("remotive", lambda: remotive(m, client)),
                         ("arbeitnow", lambda: arbeitnow(m, client, feeds["arbeitnow"]["pages"])), ("remoteok", lambda: remote_ok(m, client))):
            try:
                got = [r for r in run() if r]
            except Exception as exc:
                print(f"  !! {key}: {exc}")
                continue
            stats[feeds[key]["name"]] = len(got)
            jobs += got
    cutoff = (dt.date.today() - dt.timedelta(days=MAX_AGE_DAYS)).isoformat()
    seen, kept = set(), []
    for r in jobs:
        key = (r["company"].lower(), r["title"].lower(), r["location"].lower())
        if key in seen or (r["posted"] and r["posted"] < cutoff):
            continue
        seen.add(key)
        if not r["countries"] and r["remote"] in (None, "UNSPECIFIED"):
            continue                         # we cannot tell where it can be done from
        if not r["roles"] and len(r["skills"]) < 3:
            continue                         # nothing in it we can match a person to
        kept.append(r)
    kept.sort(key=lambda r: r["posted"] or "", reverse=True)
    for i, r in enumerate(kept, start=1):
        r["id"] = f"j{i}"
    write_texts(kept)
    for r in jobs:
        r.pop("text", None)
    sources = [{"name": b["company"], "url": board_url(b), "kind": "company"} for b in SOURCES["boards"]]
    sources += [{"name": f["name"], "url": f["url"], "kind": "feed"} for f in feeds.values()]
    data = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "jobs": kept,
            "stats": {"fetched": len(jobs), "kept": len(kept), "by_source": stats}, "sources": sources}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def write_texts(jobs: list[dict]) -> None:
    TEXTS.parent.mkdir(parents=True, exist_ok=True)
    with TEXTS.open("w", encoding="utf-8") as f:
        for r in jobs:
            sents = trim(r.get("text") or "")
            row = {"key": url_key(r["url"]), "id": r["id"], "title": r["title"], "company": r["company"], "sentences": sents, "h": text_hash(sents)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class _NoMatch:
    """--texts-only: the texts are needed, not the (slow) skill matching."""
    def roles(self, title: str) -> list[str]:
        return []

    def skills_in(self, text: str) -> list[str]:
        return []


def texts_only() -> int:
    """Re-writes the trimmed texts for the postings of the current snapshot from the cached responses (no network)."""
    fetch.OFFLINE = True
    m, feeds, found = _NoMatch(), SOURCES["feeds"], {}
    with fetch.client() as client:
        runs = [lambda b=b: BOARDS[b["ats"]](m, client, b) for b in SOURCES["boards"]]
        runs += [lambda: hacker_news(m, client), lambda: himalayas(m, client, feeds["himalayas"]["pages"]),
                 lambda: jobicy(m, client, feeds["jobicy"]["pages"]), lambda: remotive(m, client),
                 lambda: arbeitnow(m, client, feeds["arbeitnow"]["pages"]), lambda: remote_ok(m, client)]
        for run in runs:
            try:
                for r in run():
                    if r:
                        found.setdefault((r["company"].lower(), r["title"].lower(), r["location"].lower()), r["text"])
            except Exception as exc:
                print(f"  !! {exc}")
    jobs = json.loads(OUT.read_text(encoding="utf-8"))["jobs"]
    rows = [{**j, "text": found.get((j["company"].lower(), j["title"].lower(), j["location"].lower()), "")} for j in jobs]
    write_texts(rows)
    return sum(1 for r in rows if r["text"])


def board_url(board: dict) -> str:
    return {"greenhouse": f"https://boards.greenhouse.io/{board['slug']}", "lever": f"https://jobs.lever.co/{board['slug']}",
            "ashby": f"https://jobs.ashbyhq.com/{board['slug']}"}[board["ats"]]


def main() -> None:
    if "--texts-only" in sys.argv:
        n = texts_only()
        print(f"trimmed texts for {n} postings -> {TEXTS.relative_to(ROOT)}")
        return
    data = build()
    jobs = data["jobs"]
    countries = Counter(c for j in jobs for c in j["countries"])
    remote = sum(1 for j in jobs if j["remote"])
    print(f"kept {len(jobs)} of {data['stats']['fetched']} postings · {len(countries)} countries · {remote} remote")
    print("top countries:", countries.most_common(15))
    print("MY:", countries["MY"], "SG:", countries["SG"], "| remote worldwide:", sum(1 for j in jobs if j["remote"] == "WORLD"))
    print("roles:", Counter(r for j in jobs for r in j["roles"][:1]).most_common(12))
    print("levels:", Counter(j["level"] for j in jobs))
    print(f"size: {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

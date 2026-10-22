"""Opportunities: the last step of the journey — a job, or a place at university.

A person answers two questions (study or work? where?) and Path.AI lists:
* work  — open postings from public sources worldwide that can be done in that country (on site, or remotely from it),
          matched to the person's skills with the same explainable scoring as the role matches, and with the courses
          that close the gap. Searches on the big job sites of that country are one tap away.
* study — the universities of that country (ordered by how widely known they are, not by a ranking), the degree
          fields that lead towards the person's direction, how to apply and how to fund it.

The data is a dated snapshot built by scripts/opportunities (jobs.py, universities.py); nothing about the person is
stored — the profile is sent with each request, as on the matches page. When the language model has read the postings
(scripts/opportunities/enrich.py → job_facts.json), each job also carries the facts it found — skills required or nice
to have, years of experience, degree, languages, pay, work mode, visa sponsorship — every one checked against the
posting's own sentences.
"""
import hashlib
import json
import re
import urllib.parse
from functools import lru_cache

from .catalog import get_catalog
from .config import DATA
from .engine.matching import Profile, gap_hours, match_role, skill_credit

OPP_DIR = DATA / "opportunities"
REMOTE = "REMOTE"
SOFT = {"communication", "leadership", "analytical_thinking", "creative_thinking", "digital_literacy"}
READY = 70          # fit at which a posting counts as "ready to apply" (the page groups by 70 / 45)
MIN_FIT = 25
LEVEL_FILTERS = {"early": {"intern", "entry"}, "mid": {"mid"}, "senior": {"senior"}}
HISTORICAL = {"DD", "YU", "SU", "CS", "ZR", "TP", "AN", "BU", "YD"}   # former countries still found in old Wikidata records


class OppError(ValueError):
    pass


def _load(name: str) -> dict:
    path = OPP_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def url_key(url: str) -> str:
    """A posting's stable id across rebuilds (the snapshot's j1, j2… ids are renumbered every build)."""
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def with_facts(jobs: list[dict], facts: dict[str, dict]) -> list[dict]:
    """Adds what the model read in each posting; its skills (required, then nice to have) replace the keyword match."""
    for job in jobs:
        found = facts.get(url_key(job["url"]))
        if found is not None:
            job["ai"] = found
            if found.get("req") or found.get("nice"):
                job["skills"] = list(dict.fromkeys(found.get("req", []) + found.get("nice", [])))
    return jobs


@lru_cache(maxsize=1)
def data() -> dict:
    jobs = _load("jobs.json")
    unis = _load("universities.json")
    ai = _load("job_facts.json") if (OPP_DIR / "job_facts.json").exists() else {}
    jobs_meta = {k: jobs.get(k) for k in ("generated", "stats", "sources")}
    jobs_meta["ai"] = {k: ai.get(k) for k in ("model", "generated", "read")} if ai else None
    return {"jobs": with_facts(jobs.get("jobs", []), ai.get("facts", {})), "jobs_meta": jobs_meta,
            "universities": unis.get("countries", {}), "unis_meta": {k: unis.get(k) for k in ("generated", "sources")},
            "portals": _load("portals.json"), "fields": _load("fields.json")}


def where_ok(job: dict, country: str) -> str | None:
    """'local' if the job is in the country, 'remote' if it can be done from there remotely, else None.
    REMOTE ("from anywhere") only takes postings open to applicants worldwide: a "remote, US only" job is not."""
    if country == REMOTE:
        return "remote" if job["remote"] == "WORLD" else None
    if country in job["countries"]:
        return "local"
    remote = job["remote"]
    if remote == "WORLD" or (isinstance(remote, list) and country in remote):
        return "remote"
    return None


@lru_cache(maxsize=1)
def meta() -> dict:
    d = data()
    counts: dict[str, dict] = {}
    world = 0
    for job in d["jobs"]:
        for c in job["countries"]:
            counts.setdefault(c, {"jobs": 0, "remote": 0})["jobs"] += 1
        if isinstance(job["remote"], list):
            for c in job["remote"]:
                if c not in job["countries"]:
                    counts.setdefault(c, {"jobs": 0, "remote": 0})["remote"] += 1
        world += job["remote"] == "WORLD"
    for code, entry in d["universities"].items():
        counts.setdefault(code, {"jobs": 0, "remote": 0})["universities"] = entry["total"]
    countries = [{"code": c, "jobs": v["jobs"], "remote": v["remote"] + world, "universities": v.get("universities", 0)}
                 for c, v in sorted(counts.items()) if len(c) == 2 and c not in HISTORICAL]
    return {"countries": countries, "remote_world": world,
            "jobs_total": len(d["jobs"]), "jobs_updated": d["jobs_meta"].get("generated"), "jobs_sources": d["jobs_meta"].get("sources") or [],
            "unis_updated": d["unis_meta"].get("generated"), "unis_sources": d["unis_meta"].get("sources") or []}


# ---------------------------------------------------------------- work

def score_job(profile: Profile, certified: set[str], job: dict, roles: list[str], role_cache: dict) -> dict:
    """Fit of one posting: the role it was recognised as (same weighting as the role matches), blended with the
    hard skills its text asks for. Returns what the person already has and what is missing, with hours to learn."""
    catalog = get_catalog()
    best = None
    for rid in job["roles"]:
        if rid not in catalog.roles:
            continue
        if rid not in role_cache:
            role_cache[rid] = match_role(catalog, profile, rid)
        if best is None or (role_cache[rid]["fit"], rid in roles) > (best[1]["fit"], best[0] in roles):
            best = (rid, role_cache[rid])
    hard = [s for s in job["skills"] if s not in SOFT and s in catalog.skills]
    credits = {s: skill_credit(catalog, profile.skills, s, 2)["credit"] for s in hard}
    skill_fit = sum(credits.values()) / len(credits) if credits else None
    if best and skill_fit is not None:
        fit = 0.7 * best[1]["fit"] + 0.3 * skill_fit
    elif best:
        fit = best[1]["fit"]
    else:
        fit = 0.8 * (skill_fit or 0)           # no recognised role: the skills alone, discounted
    have, missing = [], {}
    if best:
        for item in sorted(best[1]["items"], key=lambda i: -i["weight"]):
            if item["status"] == "have":
                have.append(item["id"])
            elif item["weight"] >= 0.5:        # core and supporting skills; nice-to-haves are not shown as gaps
                missing[item["id"]] = item["gap_hours"]
    for s, credit in sorted(credits.items(), key=lambda kv: kv[1]):
        if credit >= 1:
            if s not in have:
                have.append(s)
        elif s not in missing and s not in have:   # partly there: the hours left to a working level
            missing[s] = gap_hours(catalog, s, 2, credit)
    return {"fit": round(fit * 100), "role": best[0] if best else None,
            "have": [{"id": s, "certified": s in certified} for s in have[:6]],
            "missing": [{"id": s, "hours": hours} for s, hours in list(missing.items())[:4]]}


def _posted(job: dict) -> int:
    return int((job["posted"] or "0").replace("-", ""))


def jobs_for(profile: Profile, certified: list[str], country: str, roles: list[str], level: str | None = None,
             limit: int = 40) -> dict:
    """Postings that can be done from `country` (or remotely, for REMOTE), relevant to the person's directions
    (`roles`) or skills, best fit first. Without any skills yet, the newest postings on those directions, unscored."""
    catalog = get_catalog()
    roles = [r for r in roles if r in catalog.roles]
    certified_set = {s for s in certified if s in catalog.skills}
    if certified_set:  # a Path.AI certificate counts as a working-level skill
        profile = profile.model_copy(update={"skills": {**profile.skills, **{s: max(2, profile.skills.get(s, 0)) for s in certified_set}}})
    mine = set(profile.skills)
    wanted = LEVEL_FILTERS.get(level or "")
    role_cache: dict = {}
    local, remote, considered = [], [], 0
    for job in data()["jobs"]:
        where = where_ok(job, country)
        if not where or (wanted and job["level"] not in wanted):
            continue
        on_path = bool(set(job["roles"]) & set(roles))
        overlap = len((mine & set(job["skills"])) - SOFT)
        # The model lists only the skills a posting asks for (≈3 per posting) where keyword matching found ≈7, so a
        # posting it has read needs one shared skill less to count as relevant.
        need = 2 if job.get("ai") else 3
        if mine:
            relevant = (on_path or overlap >= need) if roles else overlap >= need - 1
        else:
            relevant = on_path if roles else bool(job["roles"])
        if not relevant:
            continue
        considered += 1
        if mine:
            s = score_job(profile, certified_set, job, roles, role_cache)
            if s["fit"] < MIN_FIT:
                continue
        else:
            s = {"fit": None, "role": next((r for r in job["roles"] if r in roles), (job["roles"] or [None])[0]), "have": [], "missing": []}
        item = {k: job[k] for k in ("id", "title", "company", "url", "source", "posted", "location", "level", "type")}
        item["ai"] = {k: v for k, v in job.get("ai", {}).items() if k not in ("req", "nice")} or None
        item.update(s, where=where, remote=job["remote"] if isinstance(job["remote"], str) or not job["remote"] else job["remote"][:8])
        (local if where == "local" else remote).append(item)
    order = lambda j: (-(j["fit"] or 0), j["level"] == "senior", -_posted(j))
    local.sort(key=order)
    remote.sort(key=order)
    return {"country": country, "considered": considered, "scored": bool(mine), "local": local[:limit], "remote": remote[:limit],
            "counts": {"local": len(local), "remote": len(remote), "ready": sum(1 for j in local + remote if (j["fit"] or 0) >= READY)},
            "updated": data()["jobs_meta"].get("generated"), "total": len(data()["jobs"])}


SEARCH_TITLES = {"accounting_clerk": "Accounting Clerk", "ld_specialist": "Learning and Development Specialist",
                 "genai_developer": "Generative AI Developer", "teacher": "Teacher", "digital_marketing_analyst": "Digital Marketing Analyst",
                 "iot_specialist": "IoT Engineer", "ev_technician": "EV Technician", "digital_pm": "Digital Project Manager",
                 "precision_agri_technologist": "Agriculture Technologist"}


def search_title(rid: str) -> str:
    """A role title as people type it into a job site: "Financial Analyst (FP&A)" -> "Financial Analyst",
    "Data Analyst / BI Analyst" -> "Data Analyst", "Cloud / DevOps Engineer" -> "DevOps Engineer"."""
    if rid in SEARCH_TITLES:
        return SEARCH_TITLES[rid]
    title = re.sub(r"\s*\([^)]*\)", "", get_catalog().roles[rid]["title"]["en"]).strip()
    if " / " in title:
        first, second = title.split(" / ", 1)
        title = second if " " not in first else first     # "Cloud / DevOps Engineer": the first part is only a prefix
    return title


def job_portals(country: str, title: str, country_name: str) -> list[dict]:
    p = data()["portals"].get("jobs", {})
    q = urllib.parse.quote_plus(title)
    slug = "-".join(w for w in "".join(ch.lower() if ch.isalnum() else " " for ch in title).split())
    fill = lambda url: url.replace("{q}", q).replace("{slug}", slug).replace("{country}", urllib.parse.quote_plus(country_name))
    out = [{"name": x["name"], "url": fill(x["url"]), "official": bool(x.get("official"))} for x in p.get("by_country", {}).get(country, [])]
    eures = p.get("eures")
    if eures and country in eures["countries"].split():
        out.append({"name": eures["name"], "url": eures["url"], "official": True})
    for x in p.get("global", []):
        where = "Remote" if country == REMOTE else country_name
        out.append({"name": x["name"], "url": x["url"].replace("{q}", q).replace("{country}", urllib.parse.quote_plus(where)), "official": False})
    return out


# ---------------------------------------------------------------- study

def fields_for(roles: list[str], study_field: str | None) -> list[str]:
    f = data()["fields"]
    picks: list[str] = []
    if study_field:
        picks += f.get("from_study", {}).get(study_field, [])
    for rid in roles:
        picks += f.get("from_roles", {}).get(rid, [])
    out = [x for x in dict.fromkeys(picks) if x in f.get("fields", {})][:6]
    return out or ["computer_science", "business_administration", "data_science", "education"]


def study_for(country: str, roles: list[str], study_field: str | None) -> dict:
    d = data()
    entry = d["universities"].get(country) if country not in HISTORICAL else None
    if not entry:
        raise OppError("No universities listed for this country yet.")
    portals = d["portals"].get("study", {})
    local = portals.get("by_country", {}).get(country, {})
    funding = list(local.get("funding", []))
    erasmus = portals.get("erasmus")
    if erasmus and country in erasmus["countries"].split():
        funding.append({"name": erasmus["name"], "url": erasmus["url"]})
    return {"country": country, "total": entry["total"], "universities": entry["items"],
            "apply": local.get("apply", []), "funding": funding, "rankings": portals.get("global", []),
            "recommended": fields_for(roles, study_field), "fields": d["fields"].get("fields", {}),
            "updated": d["unis_meta"].get("generated"), "sources": d["unis_meta"].get("sources") or []}

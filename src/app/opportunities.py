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
import statistics
import urllib.parse
from collections import Counter
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

YEAR_PENALTY, YEAR_PENALTY_CAP = 0.08, 0.30     # per year of experience a posting asks for beyond the person's
LANGUAGE_PENALTY = 0.35                         # a language the posting requires and the person does not work in
NICE_WEIGHT = 0.5                               # a skill the posting lists as nice to have counts half


def score_job(profile: Profile, certified: set[str], job: dict, roles: list[str], role_cache: dict) -> dict:
    """Fit of one posting: the role it was recognised as (same weighting as the role matches), blended with the
    hard skills its text asks for (required ones count fully, nice-to-haves half). When the model has read the
    posting, two checks follow what it explicitly asks for: years of experience and languages. A missing requirement
    lowers the fit and is named on the card; when the person has not said, nothing is assumed.
    Returns what the person already has and what is missing, with hours to learn, and the checks."""
    catalog = get_catalog()
    ai = job.get("ai") or {}
    best = None
    for rid in job["roles"]:
        if rid not in catalog.roles:
            continue
        if rid not in role_cache:
            role_cache[rid] = match_role(catalog, profile, rid)
        if best is None or (role_cache[rid]["fit"], rid in roles) > (best[1]["fit"], best[0] in roles):
            best = (rid, role_cache[rid])
    required, nice = set(ai.get("req", [])), set(ai.get("nice", []))
    hard = [s for s in job["skills"] if s not in SOFT and s in catalog.skills]
    weight = {s: NICE_WEIGHT if s in nice and s not in required else 1.0 for s in hard}
    credits = {s: skill_credit(catalog, profile.skills, s, 2)["credit"] for s in hard}
    skill_fit = sum(weight[s] * credits[s] for s in hard) / sum(weight.values()) if hard else None
    if best and skill_fit is not None:
        fit = 0.7 * best[1]["fit"] + 0.3 * skill_fit
    elif best:
        fit = best[1]["fit"]
    else:
        fit = 0.8 * (skill_fit or 0)           # no recognised role: the skills alone, discounted

    checks = []
    asked = [s for s in hard if s in required] if required else hard
    if asked:
        got = sum(1 for s in asked if credits[s] >= 1)
        checks.append({"kind": "skills", "have": got, "of": len(asked), "ok": got >= 0.75 * len(asked)})
    if (years := ai.get("years")) is not None:
        mine = profile.years_experience
        checks.append({"kind": "years", "need": years, "have": mine, "ok": None if mine is None else mine >= years})
        if mine is not None and mine < years:
            fit -= min(YEAR_PENALTY_CAP, YEAR_PENALTY * (years - mine))
    if langs := required_languages(job):
        lacking = [code for code in langs if code not in profile.languages] if profile.languages else []
        checks.append({"kind": "languages", "need": langs, "missing": lacking, "ok": None if not profile.languages else not lacking})
        if lacking:
            fit -= LANGUAGE_PENALTY

    have, missing = [], {}
    for s in sorted(asked, key=lambda x: credits[x]) if required else []:   # what the posting requires comes first
        if credits[s] < 1:
            missing[s] = gap_hours(catalog, s, 2, credits[s])
    if best:
        for item in sorted(best[1]["items"], key=lambda i: -i["weight"]):
            if item["status"] == "have":
                if item["id"] not in missing:  # the posting asks for more than this role does: its level counts
                    have.append(item["id"])
            elif item["weight"] >= 0.5 and item["id"] not in missing:   # core and supporting skills only
                missing[item["id"]] = item["gap_hours"]
    for s, credit in sorted(credits.items(), key=lambda kv: kv[1]):
        if credit >= 1:
            if s not in have:
                have.append(s)
        elif s not in missing and s not in have and s not in nice:   # partly there: the hours left to a working level
            missing[s] = gap_hours(catalog, s, 2, credit)
    return {"fit": max(0, round(fit * 100)), "role": best[0] if best else None, "checks": checks,
            "have": [{"id": s, "certified": s in certified} for s in have[:6]],
            "missing": [{"id": s, "hours": hours} for s, hours in list(missing.items())[:4]]}


LANGUAGE_NAMES = {"en": "English", "ms": "Malay", "zh": "Mandarin Chinese", "yue": "Cantonese", "ta": "Tamil", "hi": "Hindi",
                  "ja": "Japanese", "ko": "Korean", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian", "tl": "Filipino",
                  "ar": "Arabic", "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese", "it": "Italian",
                  "nl": "Dutch", "pl": "Polish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
                  "tr": "Turkish", "ru": "Russian", "uk": "Ukrainian", "cs": "Czech", "he": "Hebrew", "el": "Greek",
                  "ro": "Romanian", "hu": "Hungarian"}


_TITLE_LANGUAGES = {"english": "en", "malay": "ms", "bahasa": "ms", "mandarin": "zh", "chinese": "zh", "cantonese": "yue", "tamil": "ta",
                    "hindi": "hi", "japanese": "ja", "korean": "ko", "thai": "th", "vietnamese": "vi", "indonesian": "id",
                    "filipino": "tl", "tagalog": "tl", "arabic": "ar", "german": "de", "french": "fr", "spanish": "es",
                    "portuguese": "pt", "italian": "it", "dutch": "nl", "polish": "pl", "swedish": "sv", "danish": "da",
                    "norwegian": "no", "finnish": "fi", "turkish": "tr", "russian": "ru", "ukrainian": "uk", "czech": "cs",
                    "hebrew": "he", "greek": "el", "romanian": "ro", "hungarian": "hu"}
_TITLE_LANGUAGE = re.compile(r"\b(" + "|".join(_TITLE_LANGUAGES) + r")\b", re.I)


def title_languages(title: str) -> list[str]:
    """Languages a job title itself names ("KYC Analyst - Japanese Speaker", "Finnish Tech Linguistic Tester")."""
    title = re.sub(r"bahasa indonesia", "indonesian", title, flags=re.I)
    return sorted({_TITLE_LANGUAGES[m.lower()] for m in _TITLE_LANGUAGE.findall(title)})


def required_languages(job: dict) -> list[str]:
    return sorted(set((job.get("ai") or {}).get("languages") or []) | set(title_languages(job["title"])))


def job_by_id(job_id: str) -> dict | None:
    return next((j for j in data()["jobs"] if j["id"] == job_id), None)


def advice_facts(profile: Profile, certified: list[str], job: dict) -> dict:
    """Everything the model may use to advise on one posting: what it asks for and what the person has."""
    catalog = get_catalog()
    certified_set = {s for s in certified if s in catalog.skills}
    if certified_set:
        profile = profile.model_copy(update={"skills": {**profile.skills, **{s: max(2, profile.skills.get(s, 0)) for s in certified_set}}})
    scored = score_job(profile, certified_set, job, [], {})
    name = lambda sid: catalog.skills[sid]["name"]["en"]
    lang = lambda codes: [LANGUAGE_NAMES.get(c, c) for c in codes]
    ai = job.get("ai") or {}
    asks: dict = {}
    if ai.get("req"):
        asks["required_skills"] = [name(s) for s in ai["req"] if s in catalog.skills]
    if ai.get("nice"):
        asks["nice_to_have_skills"] = [name(s) for s in ai["nice"] if s in catalog.skills]
    if ai.get("years") is not None:
        asks["years_of_experience"] = ai["years"]
    if ai.get("degree"):
        asks["degree"] = ai["degree"] + ("" if ai.get("degree_required", True) else " (preferred, not required)")
    if langs := required_languages(job):
        asks["languages"] = lang(langs)
    if ai.get("pay"):
        low, high, currency, per = ai["pay"]
        asks["pay"] = {"from": low, "to": high, "currency": currency, "per": per}
    if ai.get("mode"):
        asks["work_mode"] = ai["mode"]
    if ai.get("visa") is not None:
        asks["visa_sponsorship"] = ai["visa"]
    person: dict = {"skills_they_have": [name(h["id"]) for h in scored["have"]],
                    "skills_to_learn": [{"skill": name(m["id"]), "hours_to_learn": m["hours"]} for m in scored["missing"]]}
    if profile.years_experience is not None:
        person["years_of_experience"] = profile.years_experience
    if profile.languages:
        person["languages"] = lang(profile.languages)
    return {"posting": {"title": job["title"], "company": job["company"], "place": job["location"], "level": job["level"]},
            "posting_asks": asks, "person": person, "fit_percent": scored["fit"]}


# ---------------------------------------------------------------- the market for one direction
MARKET_TOP_SKILLS = 8
MIN_LOCAL_SAMPLE = 8        # fewer postings in the chosen country: the picture is drawn from the role worldwide
MIN_WORLD_SAMPLE = 10       # fewer worldwide too: no picture, rather than percentages of two postings
MIN_PAY_SAMPLE = 5


def _share(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def market_stats(jobs: list[dict], profile: Profile) -> dict:
    """What the postings for one direction ask for, from the facts the model read in them."""
    catalog = get_catalog()
    read = [j for j in jobs if j.get("ai")]
    total = len(read)
    required, nice = Counter(), Counter()
    for j in read:
        required.update(s for s in j["ai"].get("req", []) if s in catalog.skills)
        nice.update(s for s in j["ai"].get("nice", []) if s in catalog.skills)
    skills = []
    for sid, count in required.most_common(MARKET_TOP_SKILLS):
        credit = skill_credit(catalog, profile.skills, sid, 2)["credit"]    # same partial credit as the match percentages
        skills.append({"id": sid, "share": _share(count, total), "nice_share": _share(nice[sid], total), "you": credit >= 1,
                       "credit": round(credit, 3)})
    asked = sum(x["share"] for x in skills)
    years = sorted(j["ai"]["years"] for j in read if "years" in j["ai"])
    degree = sum(1 for j in read if j["ai"].get("degree") in ("bachelor", "master", "phd") and j["ai"].get("degree_required", True))
    languages = Counter(code for j in read for code in required_languages(j))
    modes = Counter(j["ai"]["mode"] for j in read if j["ai"].get("mode"))
    visa = Counter(j["ai"]["visa"] for j in read if "visa" in j["ai"])
    pay_groups: dict[tuple, list] = {}
    for j in read:
        if p := j["ai"].get("pay"):
            pay_groups.setdefault((p[2], p[3]), []).append(p)
    pay = None
    if pay_groups:
        (currency, per), rows = max(pay_groups.items(), key=lambda kv: len(kv[1]))
        if len(rows) >= MIN_PAY_SAMPLE:
            pay = {"currency": currency, "per": per, "n": len(rows), "low": round(statistics.median(r[0] for r in rows)),
                   "high": round(statistics.median(r[1] if r[1] is not None else r[0] for r in rows))}
    return {
        "n": len(jobs), "read": total, "remote": sum(1 for j in jobs if j["remote"]),
        "skills": skills, "coverage": round(sum(x["share"] * x["credit"] for x in skills) / asked, 3) if asked else None,
        "years": {"n": len(years), "median": statistics.median(years), "share_0_2": _share(sum(1 for y in years if y <= 2), len(years)),
                  "share_3_5": _share(sum(1 for y in years if 3 <= y <= 5), len(years)),
                  "share_6_plus": _share(sum(1 for y in years if y >= 6), len(years))} if years else None,
        "degree_share": _share(degree, total),
        "languages": [{"code": code, "share": _share(count, total)} for code, count in languages.most_common(5)],
        "modes": {mode: _share(count, sum(modes.values())) for mode, count in modes.most_common()},
        "visa": {"sponsors": visa[True], "no": visa[False]},
        "pay": pay,
    }


def market_for(profile: Profile, certified: list[str], country: str, rid: str) -> dict:
    """The market for one direction where the person wants to work, next to the same direction worldwide."""
    catalog = get_catalog()
    certified_set = {s for s in certified if s in catalog.skills}
    if certified_set:
        profile = profile.model_copy(update={"skills": {**profile.skills, **{s: max(2, profile.skills.get(s, 0)) for s in certified_set}}})
    role_jobs = [j for j in data()["jobs"] if rid in j["roles"]]
    here = [j for j in role_jobs if where_ok(j, country)]
    local, world = market_stats(here, profile), market_stats(role_jobs, profile)
    return {"role": rid, "country": country, "updated": data()["jobs_meta"].get("generated"),
            "here": local, "world": world,
            "basis": "here" if local["read"] >= MIN_LOCAL_SAMPLE else "world" if world["read"] >= MIN_WORLD_SAMPLE else "none",
            "you": {"years": profile.years_experience, "languages": profile.languages}}


def market_facts(market: dict, outlook_pct: float | None, country_name: str) -> dict:
    """The fact sheet for the model's market check: percentages as whole numbers, names instead of ids."""
    catalog = get_catalog()
    name = lambda sid: catalog.skills[sid]["name"]["en"]
    basis = market[market["basis"]]
    pc = lambda x: round(100 * x)
    facts = {
        "direction": catalog.roles[market["role"]]["title"]["en"],
        "where": "remote jobs open to applicants worldwide" if market["country"] == REMOTE else (country_name or market["country"]),
        "open_postings_here": market["here"]["n"], "open_postings_worldwide": market["world"]["n"],
        "scope": "this place" if market["basis"] == "here" else "worldwide",       # few postings here: the direction worldwide
        "skills_employers_require_most": [{"skill": name(x["id"]), "percent_of_postings": pc(x["share"]), "person_has_it": x["you"]}
                                          for x in basis["skills"]],
    }
    if basis["coverage"] is not None:
        facts["person_covers_percent_of_that_demand"] = pc(basis["coverage"])
    if outlook_pct is not None:
        facts["demand_growth_percent_per_year_estimate"] = round(outlook_pct)
    if basis["years"]:
        facts["years_of_experience_asked"] = {"median": basis["years"]["median"], "percent_asking_0_to_2": pc(basis["years"]["share_0_2"]),
                                              "percent_asking_6_or_more": pc(basis["years"]["share_6_plus"])}
    facts["percent_requiring_a_degree"] = pc(basis["degree_share"])
    if basis["languages"]:
        facts["languages_required"] = [{"language": LANGUAGE_NAMES.get(x["code"], x["code"]), "percent_of_postings": pc(x["share"])}
                                       for x in basis["languages"]]
    if basis["pay"]:
        facts["typical_pay"] = {**basis["pay"], "note": "median of postings that state pay"}
    else:
        facts["pay"] = "too few postings state pay to show a range"
    if basis["visa"]["sponsors"] or basis["visa"]["no"]:
        facts["visa_sponsorship_mentions"] = basis["visa"]
    person = {}
    if market["you"]["years"] is not None:
        person["years_of_experience"] = market["you"]["years"]
    if market["you"]["languages"]:
        person["languages"] = [LANGUAGE_NAMES.get(c, c) for c in market["you"]["languages"]]
    if person:
        facts["person"] = person
    return facts


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
            s = {"fit": None, "role": next((r for r in job["roles"] if r in roles), (job["roles"] or [None])[0]), "have": [], "missing": [], "checks": []}
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

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import opportunities as opp
from app.catalog import get_catalog
from app.engine.matching import Profile
from app.learn import get_learn
from app.main import app

client = TestClient(app)
catalog = get_catalog()
ROOT = Path(__file__).resolve().parents[1]
DATA = opp.data()
JOBS = DATA["jobs"]
AISYAH = Profile(skills={"bookkeeping": 3, "excel": 2, "data_entry": 3, "communication": 2, "finance_domain": 1}, current_role="accounting_clerk")
DIRECTIONS = ["data_analyst", "financial_analyst", "accounting_clerk"]


# ---------------------------------------------------------------- the snapshot
def test_job_snapshot_is_dated_attributed_and_lean():
    raw = json.loads((ROOT / "data/opportunities/jobs.json").read_text(encoding="utf-8"))
    assert raw["generated"] and raw["sources"] and len(JOBS) > 1000
    keys = {"id", "title", "company", "url", "source", "posted", "location", "countries", "remote", "level", "type", "roles", "skills"}
    for job in JOBS:
        assert set(job) == keys                       # no descriptions or other free text is stored
        assert job["url"].startswith("https://")
        assert all(re.fullmatch(r"[A-Z]{2}", c) for c in job["countries"])
        assert job["remote"] in (None, "WORLD", "UNSPECIFIED") or all(re.fullmatch(r"[A-Z]{2}", c) for c in job["remote"])
        assert job["level"] in {"intern", "entry", "mid", "senior"}
        assert set(job["roles"]) <= set(catalog.roles) and set(job["skills"]) <= set(catalog.skills)
    assert len({j["id"] for j in JOBS}) == len(JOBS)


def test_university_snapshot():
    unis = DATA["universities"]
    assert len(unis) > 150
    assert [u["name"] for u in unis["MY"]["items"][:3]] == ["Universiti Malaya", "International Islamic University Malaysia", "National University of Malaysia"]
    assert unis["HK"]["items"][0]["name"] == "University of Hong Kong"   # filed under Hong Kong, not China
    for code, entry in unis.items():
        assert re.fullmatch(r"[A-Z]{2}", code) and entry["total"] >= len(entry["items"])
        known = [u["known"] for u in entry["items"] if u["wikidata"]]
        assert known == sorted(known, reverse=True)   # best-known first
        assert all(u["site"] is None or u["site"].startswith(("https://", "http://")) for u in entry["items"])


def test_curated_links_are_https_and_fields_point_at_real_things():
    portals, fields = DATA["portals"], DATA["fields"]
    urls = [x["url"] for x in portals["jobs"]["global"]] + [portals["jobs"]["eures"]["url"], portals["study"]["erasmus"]["url"]]
    urls += [x["url"] for lst in portals["jobs"]["by_country"].values() for x in lst]
    urls += [x["url"] for c in portals["study"]["by_country"].values() for x in c["apply"] + c["funding"]]
    assert urls and all(u.startswith("https://") for u in urls)
    courses = set(get_learn().courses)
    for fid, f in fields["fields"].items():
        assert f["label"]["en"] and f["label"]["ms"] and f["label"]["zh"] and f["search"]
        assert set(f["prepare"]) <= courses, fid
    assert set(fields["from_roles"]) == set(catalog.roles)
    assert set(fields["from_study"]) == {f["id"] for f in catalog.study_fields}
    assert all(set(v) <= set(fields["fields"]) for v in [*fields["from_roles"].values(), *fields["from_study"].values()])


# ---------------------------------------------------------------- where a job can be done from
def test_where_a_job_can_be_done_from():
    on_site = {"countries": ["MY"], "remote": None}
    eu_remote = {"countries": ["DE"], "remote": ["DE", "FR", "NL"]}
    anywhere = {"countries": [], "remote": "WORLD"}
    unclear = {"countries": [], "remote": "UNSPECIFIED"}
    assert opp.where_ok(on_site, "MY") == "local" and opp.where_ok(on_site, "SG") is None
    assert opp.where_ok(eu_remote, "DE") == "local" and opp.where_ok(eu_remote, "FR") == "remote" and opp.where_ok(eu_remote, "MY") is None
    assert opp.where_ok(anywhere, "MY") == "remote" and opp.where_ok(anywhere, opp.REMOTE) == "remote"
    # "remote from anywhere" means anywhere: a remote job limited to some countries, or one that does not say, is left out
    assert opp.where_ok(eu_remote, opp.REMOTE) is None and opp.where_ok(unclear, opp.REMOTE) is None and opp.where_ok(unclear, "MY") is None


# ---------------------------------------------------------------- matching
def test_jobs_are_ranked_by_fit_and_explained():
    res = opp.jobs_for(AISYAH, [], "MY", DIRECTIONS)
    assert res["scored"] and res["local"]
    for side in ("local", "remote"):
        fits = [j["fit"] for j in res[side]]
        assert fits == sorted(fits, reverse=True) and all(opp.MIN_FIT <= f <= 100 for f in fits)
    jobs = {j["id"]: j for j in JOBS}
    for j in res["local"]:
        assert "MY" in jobs[j["id"]]["countries"] and j["where"] == "local"
        have = {h["id"] for h in j["have"]}
        assert have <= set(AISYAH.skills) and not have & {m["id"] for m in j["missing"]}
        assert all(m["hours"] > 0 for m in j["missing"])
    for j in res["remote"]:
        assert j["where"] == "remote" and (jobs[j["id"]]["remote"] == "WORLD" or "MY" in jobs[j["id"]]["remote"])
    best = res["local"][0]
    assert best["fit"] >= opp.READY and "accounting_clerk" in jobs[best["id"]]["roles"]


def test_a_certificate_counts_as_a_working_level_skill():
    profile = Profile(skills={"excel": 2, "communication": 2, "statistics": 1}, current_role="admin_assistant")
    before = {j["id"]: j for j in opp.jobs_for(profile, [], "SG", ["data_analyst"])["local"]}
    after = {j["id"]: j for j in opp.jobs_for(profile, ["sql"], "SG", ["data_analyst"])["local"]}
    asks_sql = [i for i in after if "sql" in next(j["skills"] for j in JOBS if j["id"] == i) and i in before]
    assert asks_sql
    for i in asks_sql:
        assert after[i]["fit"] > before[i]["fit"]
        assert {"id": "sql", "certified": True} in after[i]["have"]
        assert "sql" not in {m["id"] for m in after[i]["missing"]}


def test_level_filter_and_remote_anywhere():
    early = opp.jobs_for(AISYAH, [], "SG", DIRECTIONS, level="early")
    levels = {j["id"]: j["level"] for j in JOBS}
    assert all(levels[j["id"]] in {"intern", "entry"} for j in early["local"] + early["remote"])
    anywhere = opp.jobs_for(AISYAH, [], opp.REMOTE, DIRECTIONS)
    remote = {j["id"]: j["remote"] for j in JOBS}
    assert not anywhere["local"] and all(remote[j["id"]] == "WORLD" for j in anywhere["remote"])


def test_without_skills_the_newest_postings_on_the_chosen_paths_are_shown_unscored():
    res = opp.jobs_for(Profile(), [], "SG", ["data_analyst", "data_scientist"])
    assert not res["scored"] and res["local"]
    assert all(j["fit"] is None and j["role"] in {"data_analyst", "data_scientist"} for j in res["local"])
    dates = [j["posted"] or "" for j in res["local"] if j["level"] != "senior"]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------- job sites and study
def test_job_site_searches():
    assert opp.search_title("financial_analyst") == "Financial Analyst"
    assert opp.search_title("data_analyst") == "Data Analyst"
    assert opp.search_title("cloud_devops_engineer") == "DevOps Engineer"
    assert opp.search_title("ml_engineer") == "Machine Learning Engineer"
    links = {p["name"]: p for p in opp.job_portals("MY", "Data Analyst", "Malaysia")}
    assert links["JobStreet Malaysia"]["url"] == "https://my.jobstreet.com/data-analyst-jobs"
    assert links["LinkedIn Jobs"]["url"] == "https://www.linkedin.com/jobs/search/?keywords=Data+Analyst&location=Malaysia"
    assert links["MYFutureJobs"]["official"]
    assert "EURES (EU job mobility portal)" in {p["name"] for p in opp.job_portals("DE", "Data Analyst", "Germany")}
    remote = opp.job_portals(opp.REMOTE, "Data Analyst", "")
    assert [p["name"] for p in remote] == ["LinkedIn Jobs"] and remote[0]["url"].endswith("location=Remote")


def test_study_lists_universities_degree_fields_and_how_to_apply():
    my = opp.study_for("MY", ["data_analyst"], None)
    assert my["universities"][0]["name"] == "Universiti Malaya"
    assert my["recommended"][:3] == ["data_science", "business_analytics", "statistics"]
    assert {"UPU (public universities, Malaysian students)", "EMGS — Education Malaysia (international students)"} <= {x["name"] for x in my["apply"]}
    student = opp.study_for("GB", [], "it")
    assert student["recommended"][0] == "computer_science" and "UCAS" in {x["name"] for x in student["apply"]}
    de = opp.study_for("DE", [], "engineering")
    assert any("Erasmus Mundus" in x["name"] for x in de["funding"])
    assert len(opp.study_for("MY", list(catalog.roles), "it")["recommended"]) <= 6
    with pytest.raises(opp.OppError):
        opp.study_for("XX", [], None)


# ---------------------------------------------------------------- API
def test_api():
    meta = client.get("/api/next/meta").json()
    my = next(c for c in meta["countries"] if c["code"] == "MY")
    assert my["jobs"] > 0 and my["universities"] > 100 and meta["remote_world"] > 0 and meta["jobs_updated"]
    body = {"profile": AISYAH.model_dump(), "certified": ["sql"], "country": "MY", "roles": DIRECTIONS, "country_name": "Malaysia"}
    res = client.post("/api/next/jobs", json=body).json()
    assert res["local"] and res["search_title"] == "Data Analyst" and res["portals"]
    for bad in ({"country": "Malaysia"}, {"country": "my"}, {"level": "expert"}, {"roles": ["x"] * 9}):
        assert client.post("/api/next/jobs", json={**body, **bad}).status_code == 422
    study = client.post("/api/next/study", json={"country": "SG", "roles": ["software_developer"]}).json()
    assert study["universities"] and study["recommended"][0] == "software_engineering"
    assert client.post("/api/next/study", json={"country": "XX"}).status_code == 404
    assert client.post("/api/next/study", json={"country": "REMOTE"}).status_code == 422


def test_every_listed_country_has_a_flag_image():
    codes = {c["code"] for c in client.get("/api/next/meta").json()["countries"]}
    assert len(codes) > 150 and not codes & opp.HISTORICAL           # no East Germany or Yugoslavia listed twice as "Germany", "Serbia"
    assert not [c for c in sorted(codes) if not (ROOT / "static/flags" / f"{c.lower()}.svg").is_file()]


def test_the_job_skill_prefilter_never_changes_what_is_found():
    from scripts.opportunities.jobs import Matcher, trigger
    assert trigger(r"\bsql\b(?!\s*account)") == "sql"          # text inside a look-ahead is not required
    assert trigger("cyber ?security") == "security" and trigger(r"\bplcs?\b") == "plc" and trigger("a|b") is None
    m = Matcher()
    samples = ["We use SQL Server, Python and Power BI every day.", "SQL account manager wanted.", "Lean Six Sigma green belt; SPC, 5S and kaizen.",
               "PLC and SCADA programming, ladder logic, HMI screens.", "Cybersecurity analyst (SOC, SIEM).", "Kami perlukan kerani akaun, 会计 经验.",
               "Talent acquisition partner for our people operations team.", "AML/KYC analyst, financial crime and compliance."]
    for text in samples:
        full = [sid for sid, (_, patterns) in m.skills.items() if any(p.search(text) for p in patterns)]
        assert m.skills_in(text) == full, text

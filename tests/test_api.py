from fastapi.testclient import TestClient

from app.catalog import get_catalog
from app.main import app

client = TestClient(app)
catalog = get_catalog()


def persona_body(pid="aisyah", **extra):
    p = next(x for x in catalog.personas["personas"] if x["id"] == pid)
    profile = {k: p[k] for k in ("skills", "interests", "sdg_priorities", "current_role", "hours_per_week")}
    return {"profile": profile, **extra}


def test_meta_lists_dated_sources():
    meta = client.get("/api/meta").json()
    assert meta["as_of_default"] in meta["as_of_options"]
    assert meta["signals"]["hn"]["posts"] > 1000 and meta["signals"]["hn"]["fetched_at"]
    assert meta["llm"]["mode"] in {"rules", "llm"}


def test_radar_covers_every_skill_with_a_ring():
    radar = client.post("/api/radar", json={"scenario": "fast"}).json()
    assert len(radar["skills"]) == len(catalog.skills)
    assert {s["ring"] for s in radar["skills"]} <= {"surging", "rising", "stable", "declining"}


def test_match_is_explained_and_cited():
    res = client.post("/api/match", json=persona_body()).json()
    ranks = [r["rank"] for r in res["roles"]]
    assert ranks == sorted(ranks)
    for r in res["roles"][:8]:
        assert r["explanation"] and r["sources"][0]["id"] == "S1"
        assert "[S1]" in r["explanation"]
    assert res["current"]["id"] == "accounting_clerk"


def test_pathway_and_team_views():
    res = client.post("/api/pathway", json=persona_body(role_id="automation_specialist")).json()
    assert res["steps"] and res["weeks"] > 0
    team = client.post("/api/team", json={}).json()
    assert len(team["members"]) == 8 and team["skill_gaps"]


def test_unknown_role_and_bad_upload_are_rejected():
    assert client.post("/api/pathway", json=persona_body(role_id="astronaut")).status_code == 404
    assert client.post("/api/profile/parse", files={"file": ("cv.exe", b"MZ")}).status_code == 400


def test_wizard_data_is_exposed_and_prefill_roles_exist():
    meta = client.get("/api/meta").json()
    role_ids = {r["id"] for r in meta["roles"]}
    for rid in ("accounting_clerk", "admin_assistant", "customer_service_rep", "cashier", "teacher", "graphic_designer"):
        assert rid in role_ids, f"popular job {rid} missing"
    assert all(r["skills"] for r in meta["roles"]), "every role can pre-fill a skill set"
    assert len(meta["interest_tiles"]) == 8 and meta["study_fields"]
    skill_ids = {s["id"] for s in meta["skills"]}
    assert all(sid in skill_ids for f in meta["study_fields"] for sid in f["skills"])


def test_cited_claims_name_their_page_and_malaysia_gets_its_own_numbers():
    for cid, claim in catalog.claims.items():
        assert claim.get("page") or catalog.sources[claim["source"]]["kind"] == "press release", cid
    body = persona_body(role_id="genai_developer", lang="en")
    res = client.post("/api/explain", json=body).json()
    my = next(s for s in res["sources"] if "p. 168" in s["label"])
    assert my["url"].endswith("WEF_Future_of_Jobs_Report_2025.pdf#page=168")
    assert f"grow by 29% (net) by 2030 [{my['id']}]" in res["text"]
    ms = client.post("/api/explain", json={**body, "lang": "ms"}).json()["text"]
    assert "berkembang 29%" in ms and "Laporan WEF 2025" in ms
    esg = client.post("/api/explain", json={**body, "role_id": "esg_analyst", "lang": "ms"}).json()["text"]
    assert "Laporan WEF 2023" in esg            # that claim is from the 2023 report


def test_the_current_job_shows_what_employers_in_malaysia_expect():
    body = persona_body()
    body["profile"]["current_role"] = "data_entry_clerk"
    cur = client.post("/api/match", json=body).json()["current"]
    assert cur["wef_my"]["job"] == "Data Entry Clerks" and cur["wef_my"]["net_growth_pct"] == -28
    assert cur["wef_my"]["link"].endswith("#page=168")
    body["profile"]["current_role"] = "teacher"
    assert client.post("/api/match", json=body).json()["current"]["wef_my"] is None


def test_current_job_is_never_recommended_back():
    body = persona_body()
    body["profile"]["current_role"] = "data_analyst"
    ids = [r["id"] for r in client.post("/api/match", json=body).json()["roles"]]
    assert "data_analyst" not in ids
    body["role_id"] = "data_analyst"
    assert client.post("/api/explain", json=body).status_code == 404


def test_cards_show_the_same_hours_as_the_plan():
    res = client.post("/api/match", json=persona_body()).json()
    top = res["roles"][0]
    plan = client.post("/api/pathway", json=persona_body(role_id=top["id"])).json()
    assert top["plan_hours"] == plan["total_hours"]


def test_meta_carries_what_the_goal_explainer_needs():
    meta = client.get("/api/meta").json()
    goal4 = next(g for g in meta["sdg_goals"] if g["goal"] == 4)
    assert goal4["statement"]["zh"] and goal4["essence"]["ms"] and goal4["url"].endswith("goal4")
    assert meta["sdg_targets_local"]["zh"]["4.4"] and meta["sdg_targets_local"]["ms"]["8.5"]
    skills = {s["id"]: s for s in meta["skills"]}
    assert {"goal": 4, "target": "4.4"}.items() <= skills["digital_literacy"]["sdgs"][0].items()


def test_a_refresh_reports_what_it_changed(tmp_path, monkeypatch):
    import asyncio
    import json
    from app.signals import refresh as r
    write = lambda path, data: path.write_text(json.dumps(data))
    hn, oa, meta = tmp_path / "hn.json", tmp_path / "openalex.json", tmp_path / "meta.json"
    write(hn, {"months": {"2026-09": {"posts": 400}, "2026-10": {"posts": 300}}})
    write(oa, {"buckets": {"2026H1": {"counts": {"baseline": 1000, "agents": 50}}}})
    for name, path in (("HN_FILE", hn), ("OPENALEX_FILE", oa), ("META_FILE", meta)):
        monkeypatch.setattr(r, name, path)

    async def a_new_month(*args, **kwargs):          # the November thread appears, October gets 20 more posts
        write(hn, {"months": {"2026-09": {"posts": 400}, "2026-10": {"posts": 320}, "2026-11": {"posts": 50}}})
        return {"posts": 770}

    monkeypatch.setattr(r, "refresh_hn", a_new_month)
    out = asyncio.run(r.refresh(openalex=False, log=lambda *_: None))
    assert out["hn"]["status"] == "ok"
    assert out["change"]["before"] == {"posts": 700, "months": 2, "month": "2026-10", "month_posts": 300, "half": "2026H1", "papers": 1000}
    assert out["change"]["after"] == {"posts": 770, "months": 3, "month": "2026-11", "month_posts": 50, "half": "2026H1", "papers": 1000}
    assert json.loads(meta.read_text())["change"]["after"]["posts"] == 770      # kept for the page

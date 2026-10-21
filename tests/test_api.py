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

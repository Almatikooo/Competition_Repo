import pytest

from app.catalog import get_catalog
from app.engine.forecast import Signals, compute_outlook, month_add
from app.engine.matching import Profile, Weights, match_role, rank_roles
from app.engine.pathway import build_pathway

catalog = get_catalog()
signals = Signals()
LATEST = signals.latest()
OUT = compute_outlook(catalog, signals, LATEST)


def persona(pid: str) -> Profile:
    p = next(x for x in catalog.personas["personas"] if x["id"] == pid)
    return Profile(skills=p["skills"], interests=p["interests"], sdg_priorities=p["sdg_priorities"],
                   current_role=p["current_role"], hours_per_week=p["hours_per_week"])


def test_trend_data_is_present_and_dated():
    assert LATEST is not None
    assert signals.hn["months"][LATEST]["fetched_at"]
    assert signals.openalex["buckets"]


def test_scenarios_move_complements_up_and_substitutes_down():
    g = OUT["skills"]["genai_apps"]["growth"]
    assert g["fast"] > g["moderate"] > g["slow"]
    d = OUT["skills"]["data_entry"]["growth"]
    assert d["fast"] < d["moderate"] < d["slow"] < 0


def test_output_changes_when_trend_data_changes():
    earlier = compute_outlook(catalog, signals, month_add(LATEST, -6))
    moved = [sid for sid in catalog.skills
             if abs(earlier["skills"][sid]["growth"]["moderate"] - OUT["skills"][sid]["growth"]["moderate"]) > 0.005]
    assert len(moved) >= 5


def test_every_estimate_has_an_uncertainty_band():
    for s in OUT["skills"].values():
        for scen in catalog.scenarios:
            assert s["band"][scen] > 0


def test_full_profile_fits_and_empty_profile_does_not():
    role = catalog.roles["data_analyst"]
    full = Profile(skills={i["id"]: 3 for i in role["skills"]})
    assert match_role(catalog, full, "data_analyst")["fit"] == pytest.approx(1.0)
    assert match_role(catalog, Profile(), "data_analyst")["fit"] == 0


def test_transferable_credit_is_capped():
    m = match_role(catalog, Profile(skills={"excel": 3}), "data_analyst")
    data_analysis = next(i for i in m["items"] if i["id"] == "data_analysis")
    assert 0 < data_analysis["credit"] <= 0.5
    assert data_analysis["via"] == "excel"


def test_demographics_cannot_influence_ranking():
    base = persona("aisyah").model_dump()
    with_demo = Profile(**{**base, "age": 58, "gender": "female", "ethnicity": "any", "location": "Kelantan"})
    a = rank_roles(catalog, OUT, Profile(**base), Weights(), "moderate")
    b = rank_roles(catalog, OUT, with_demo, Weights(), "moderate")
    assert [(r["id"], r["total"]) for r in a] == [(r["id"], r["total"]) for r in b]


def test_robust_flag_matches_ranks():
    for r in rank_roles(catalog, OUT, persona("kavitha"), Weights(), "moderate"):
        assert r["robust"] == all(x <= 5 for x in r["rank_by_scenario"].values())


@pytest.mark.parametrize("pid", ["aisyah", "weijie", "kavitha", "hafiz", "nurul"])
def test_pathways_only_use_catalogued_resources_in_prerequisite_order(pid):
    profile = persona(pid)
    top = rank_roles(catalog, OUT, profile, Weights(), "moderate")[0]["id"]
    plan = build_pathway(catalog, OUT, profile, top, "moderate")
    seen = set()
    for step in plan["steps"]:
        for pre in catalog.skills[step["skill"]]["prereqs"]:
            if any(s["skill"] == pre for s in plan["steps"]):
                assert pre in seen, f"{pre} must come before {step['skill']}"
        seen.add(step["skill"])
        for res in [step["resource"], step["credential"], *step["alternatives"]]:
            if res:
                assert catalog.resources[res["id"]]["url"] == res["url"]
    assert plan["total_hours"] == sum(s["hours"] for s in plan["steps"])
    assert plan["sdg_contribution"], "every pathway shows its SDG contribution"


def test_personas_get_plausible_top_roles():
    def top3(pid):
        return {r["id"] for r in rank_roles(catalog, OUT, persona(pid), Weights(), "moderate")[:3]}
    assert {"automation_specialist", "financial_analyst", "data_analyst"} & top3("aisyah")
    assert {"ev_technician", "solar_pv_technician", "renewable_energy_engineer"} & top3("weijie")
    assert {"customer_success_manager", "ld_specialist", "digital_pm"} & top3("kavitha")

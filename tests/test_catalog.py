import json
import re

from app.catalog import get_catalog
from app.config import DATA

catalog = get_catalog()


def test_catalog_is_consistent():
    assert catalog.validate() == []


def test_core_skills_of_every_target_role_have_a_verified_resource():
    for role in catalog.roles.values():
        if role["kind"] != "target":
            continue
        for item in role["skills"]:
            if item["w"] >= 1.0:
                assert catalog.resources_for(item["id"]), f"{role['id']}: no resource for core skill {item['id']}"


def test_skills_without_resources_are_a_deliberate_short_list():
    # The pathway says "no verified resource" for these instead of inventing a course.
    missing = {sid for sid in catalog.skills if not catalog.resources_for(sid)}
    assert missing == {"data_entry", "graphic_design"}


def test_every_resource_is_https_and_has_cost_and_hours():
    for r in catalog.resources.values():
        assert r["url"].startswith("https://"), r["id"]
        assert r["cost"] in {"free", "free_audit", "low_cost", "fee"}
        assert r["hours"] > 0


def test_every_role_links_to_a_real_sdg_target():
    for role in catalog.roles.values():
        assert role["sdgs"]
        for link in role["sdgs"]:
            assert link["target"] in catalog.sdg_targets
            assert 1 <= catalog.goal_of(link["target"]) <= 17
            assert link["why"]


def test_personas_are_synthetic_and_contain_no_contact_details():
    raw = (DATA / "personas.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "SYNTHETIC" in data["_note"]
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", raw), "no e-mail addresses in demo data"
    assert not re.search(r"\+?6?01\d[- ]?\d{3,4}[- ]?\d{4}", raw), "no Malaysian phone numbers in demo data"
    for p in data["personas"]:
        assert "synthetic profile" in p["cv_text"]

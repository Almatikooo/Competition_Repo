"""Loads and validates the curated catalogs (skills, roles, resources, SDGs, sources).

The catalogs are the system's ground truth: the recommender and the language model may only
reference ids that exist here, which is how we guarantee that no job, course or SDG target is invented.
"""
import json
import re
from functools import lru_cache

from .config import CATALOG_DIR, DATA

_REGEX_CHARS = set("\\()[]|?*+")


def _load(name: str) -> dict:
    return json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))


def alias_regex(alias: str) -> re.Pattern:
    """Plain aliases match as whole words; aliases containing regex syntax are used as-is."""
    alias = alias.lower()
    if _REGEX_CHARS & set(alias):
        return re.compile(alias, re.IGNORECASE)
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", re.IGNORECASE)


class Catalog:
    def __init__(self) -> None:
        skills = _load("skills.json")
        roles = _load("roles.json")
        resources = _load("resources.json")
        sdgs = _load("sdgs.json")
        caps = _load("capabilities.json")
        sources = _load("sources.json")

        self.skill_categories: dict = skills["categories"]
        self.skills: dict[str, dict] = {s["id"]: s for s in skills["skills"]}
        self.roles: dict[str, dict] = {r["id"]: r for r in roles["roles"]}
        self.interest_tags: list[str] = roles["interest_tags"]
        self.interest_tiles: list[dict] = roles.get("interest_tiles", [])
        self.study_fields: list[dict] = roles.get("study_fields", [])
        self.resources: dict[str, dict] = {r["id"]: r for r in resources["resources"]}
        self.support: list[dict] = resources["support"]
        self.resources_checked: str = resources.get("checked", "")
        self.sdg_goals: dict[int, dict] = {g["goal"]: g for g in sdgs["goals"]}
        self.sdg_targets: dict[str, str] = sdgs["targets"]
        self.capabilities: list[dict] = caps["topics"]
        self.capability_baseline: dict = caps["baseline"]
        self.scenarios: dict[str, dict] = {s["id"]: s for s in caps["scenarios"]}
        self.model: dict = caps["model"]
        self.sources: dict[str, dict] = sources["sources"]
        self.claims: dict[str, dict] = sources["claims"]
        self.personas: dict = json.loads((DATA / "personas.json").read_text(encoding="utf-8"))

        self.alias_patterns = {sid: [alias_regex(a) for a in s["aliases"]] for sid, s in self.skills.items()}
        self.hn_skill_patterns = {sid: re.compile(s["hn"], re.IGNORECASE) for sid, s in self.skills.items() if s.get("hn")}
        self.hn_role_patterns = {rid: re.compile(r["hn"], re.IGNORECASE) for rid, r in self.roles.items() if r.get("hn")}

        # Symmetric transferable-skill graph: related[a][b] = weight of credit b gives towards a.
        self.related: dict[str, dict[str, float]] = {sid: {} for sid in self.skills}
        for sid, s in self.skills.items():
            for other, w in s.get("related", {}).items():
                self.related[sid][other] = max(self.related[sid].get(other, 0.0), w)
                self.related[other][sid] = max(self.related[other].get(sid, 0.0), w)

        problems = self.validate()
        if problems:
            raise ValueError("Catalog validation failed:\n" + "\n".join(problems))

    @staticmethod
    def goal_of(target: str) -> int:
        return int(target.split(".")[0])

    def validate(self) -> list[str]:
        problems = []
        cap_ids = {c["id"] for c in self.capabilities}
        for sid, s in self.skills.items():
            for ref in s.get("prereqs", []) + list(s.get("related", {})):
                if ref not in self.skills:
                    problems.append(f"skill {sid}: unknown reference {ref}")
            for cap in s.get("ai", {}):
                if cap not in cap_ids:
                    problems.append(f"skill {sid}: unknown capability {cap}")
            if s.get("wef") and s["wef"] not in self.claims:
                problems.append(f"skill {sid}: unknown claim {s['wef']}")
            if s.get("category") not in self.skill_categories:
                problems.append(f"skill {sid}: unknown category")
            for link in s.get("sdgs", []):
                if link["target"] not in self.sdg_targets:
                    problems.append(f"skill {sid}: unknown SDG target {link['target']}")
        for rid, r in self.roles.items():
            for item in r["skills"]:
                if item["id"] not in self.skills:
                    problems.append(f"role {rid}: unknown skill {item['id']}")
            for link in r.get("sdgs", []):
                if link["target"] not in self.sdg_targets:
                    problems.append(f"role {rid}: unknown SDG target {link['target']}")
            if not r.get("sdgs"):
                problems.append(f"role {rid}: no SDG link")
            if r.get("wef") and r["wef"] not in self.claims:
                problems.append(f"role {rid}: unknown claim {r['wef']}")
        for res_id, res in self.resources.items():
            for sid in res["skills"]:
                if sid not in self.skills:
                    problems.append(f"resource {res_id}: unknown skill {sid}")
        for tile in self.interest_tiles:
            for tag in tile["tags"]:
                if tag not in self.interest_tags:
                    problems.append(f"interest tile {tile['id']}: unknown tag {tag}")
        for field in self.study_fields:
            for sid in field["skills"]:
                if sid not in self.skills:
                    problems.append(f"study field {field['id']}: unknown skill {sid}")
        for p in self.personas["personas"]:
            for sid in p["skills"]:
                if sid not in self.skills:
                    problems.append(f"persona {p['id']}: unknown skill {sid}")
        return problems

    def resources_for(self, skill_id: str) -> list[dict]:
        return [r for r in self.resources.values() if skill_id in r["skills"]]


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    return Catalog()

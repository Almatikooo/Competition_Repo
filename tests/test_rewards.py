"""Rewards (src/static/rewards.js): 30 gifts from cheap to a MacBook, points from achievements pay at most half a price,
and every gift is named and described in every interface language."""
import re
from pathlib import Path

from test_badges import catalog as badge_catalog

STATIC = Path(__file__).resolve().parents[1] / "src" / "static"


def gifts() -> list[dict]:
    js = (STATIC / "rewards.js").read_text(encoding="utf-8")
    return [{"id": m[1], "cat": m[2], "icon": m[3], "price": int(m[4])}
            for m in re.finditer(r'^\s*G\("([a-z_]+)", "([a-z]+)", "([A-Za-z]+)", (\d+)\),', js, re.M)]


def points_per_tier() -> dict[int, int]:
    js = (STATIC / "badges.js").read_text(encoding="utf-8")
    return {int(k): int(v) for k, v in re.findall(r"(\d): (\d+)", re.search(r"export const POINTS = \{([^}]*)\}", js)[1])}


def test_thirty_gifts_from_cheap_to_a_macbook():
    items = gifts()
    assert len(items) == 30 and len({g["id"] for g in items}) == 30
    assert [g["price"] for g in items] == sorted(g["price"] for g in items)          # cheapest first
    assert items[0]["price"] <= 10 and items[-1]["id"] == "macbook" and items[-1]["price"] == max(g["price"] for g in items)
    assert {g["cat"] for g in items} == {"learn", "tech", "life", "merch"}


def test_points_pay_at_most_half_and_the_macbook_takes_nearly_every_medal():
    js = (STATIC / "rewards.js").read_text(encoding="utf-8")
    assert "MAX_SHARE = 0.5" in js and "Math.floor(price * MAX_SHARE)" in js
    points = points_per_tier()
    assert points == {1: 10, 2: 50, 3: 200}
    total = sum(points[b["tier"]] for b in badge_catalog())
    half_macbook = gifts()[-1]["price"] // 2
    assert total == 2950 and 0.8 * total < half_macbook <= total                     # reachable, but only for legends


def test_every_gift_has_words_in_every_language_and_an_icon():
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    words = i18n[i18n.index("const REWARDS = {"):]
    icons = (STATIC / "core.js").read_text(encoding="utf-8")
    icons = icons[icons.index("const ICONS = {"):icons.index("export function icon(")]
    for g in gifts():
        for key in (f"rw_i_{g['id']}", f"rw_d_{g['id']}", f"rw_cat_{g['cat']}"):
            assert len(re.findall(rf"\b{key}: ", words)) == 3, key
        assert re.search(rf"\b{g['icon']}: \"", icons), g["icon"]

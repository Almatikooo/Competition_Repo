"""The achievements (src/static/badges.js): 100 medals, 70 bronze, 25 silver and 5 gold, each with a name, a description
and an icon in every interface language."""
import re
from collections import Counter
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "static"


def catalog() -> list[dict]:
    out = []
    for line in (STATIC / "badges.js").read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*B\("([a-z0-9_]+)", ([123]), "([a-z]+)", "([A-Za-z]+)", (\d+),', line)
        if m:
            shared = re.search(r'\bd: "([a-z_]+)"', line)
            out.append({"id": m[1], "tier": int(m[2]), "group": m[3], "icon": m[4], "goal": int(m[5]),
                        "text": f"bd_{shared[1] if shared else m[1]}"})
    return out


def test_there_are_100_achievements_70_bronze_25_silver_5_gold():
    badges = catalog()
    assert len(badges) == 100 and len({b["id"] for b in badges}) == 100
    assert Counter(b["tier"] for b in badges) == {1: 70, 2: 25, 3: 5}
    assert {b["id"] for b in badges if b["tier"] == 3} == {"dream", "l500", "cert10", "s100", "all"}
    assert next(b for b in badges if b["id"] == "all")["goal"] == 99            # every other one


def test_every_achievement_has_words_in_every_language_and_an_icon():
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    words = i18n[i18n.index("const ACHIEVEMENTS = {"):]
    icons = (STATIC / "core.js").read_text(encoding="utf-8")
    icons = icons[icons.index("const ICONS = {"):icons.index("export function icon(")]
    for b in catalog():
        for key in (f"bt_{b['id']}", b["text"], f"ach_group_{b['group']}"):
            assert len(re.findall(rf"\b{key}: ", words)) == 3, key                # English, Malay and Chinese
        assert re.search(rf"\b{b['icon']}: \"", icons), b["icon"]

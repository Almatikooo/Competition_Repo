"""Cuts a job posting down to the sentences that state requirements and terms, so the model reads about 3× less.

Facts come first — pay, visa or right to work, years of experience, degrees, languages — then other requirement-like
sentences (skills, duties, work mode), up to CAP characters, in the posting's own order. Company blurbs, benefits and
legal boilerplate are dropped. On the 19.5k-posting snapshot of 2026-10-21 this means ≈9.4M tokens instead of ≈30M,
while keeping the pay line in 99% of the postings that state pay, visa lines in 98% and experience, degree and
language lines in 92–94%.
"""
import hashlib
import re

from app.opportunities import url_key  # noqa: F401  (re-exported: one stable posting id for scripts and app)

CAP = 2500
LONG = 400            # longer "sentences" (flattened lists) are cut at commas or spaces

CURRENCY = r"(?:RM|MYR|S\$|SGD|US\$|USD|A\$|AU\$|AUD|C\$|CA\$|CAD|HK\$|HKD|NZ\$|NZD|\$|€|EUR|£|GBP|₹|INR|¥|JPY|CNY|RMB|CHF|SEK|PLN)"
AMOUNT = r"\d[\d,.]*\s?[kK]?"
FACTS = re.compile(
    rf"{CURRENCY}\s?{AMOUNT}|\b{AMOUNT}\s?(?:MYR|SGD|USD|EUR|GBP|AUD|CAD|INR)\b|\bgaji\b|\bsalary\b|\bpay range\b|\bcompensation\b"
    r"|\b\d{1,2}\s?\+?\s?(?:(?:-|–|to)\s?\d{1,2}\s?)?(?:years?|yrs?|tahun)\b"
    r"|\b(?:bachelor'?s?|degree|diploma|master'?s?|ph\.?d|doctorate|b\.?sc|m\.?sc|mba|ijazah|sarjana|spm|stpm)\b"
    r"|\bvisa\b|\bsponsor|\bwork permit|\bright to work|\bwork authori[sz]ation|\brelocat"
    r"|\b(?:english|malay|bahasa|mandarin|chinese|cantonese|tamil|german|french|spanish|japanese|korean|dutch|portuguese"
    r"|italian|arabic|hindi|thai|vietnamese|indonesian|polish|swedish|turkish)\b|中文|普通话|华语|日本語",
    re.I)
KEEP = re.compile(
    r"experience|qualif|requir|must|should have|you have|you.ll (?:need|bring)|ideal|proficien|fluent|skills?|knowledge"
    r"|familiar|ability to|nice to have|bonus|plus|certif|responsib|you will|what you.ll do|remote|hybrid|on-?site|office"
    r"|pengalaman|kelayakan|kemahiran|syarat|tanggungjawab|要求|经验|技能",
    re.I)
DROP = re.compile(
    r"equal opportunity|equal employment|\beeo\b|accommodation|discriminat|race, colou?r|veteran status|privacy (?:notice|policy)"
    r"|\bgdpr\b|recruitment agenc|e-verify|background check|401\(?k\)?|health insurance|dental|paid time off|\bpto\b"
    r"|parental leave|wellness|perks",
    re.I)
# Sentence ends and list bullets; "Node.js", "4.5k" and "Requirements: 3+ years" stay whole.
SPLIT = re.compile(r"(?<=[.!?•])\s+|(?<=[。！？])|\s+[•·▪●◦]\s+|\s+-\s+(?=[A-Z])")


def sentences(text: str) -> list[str]:
    out = []
    for part in SPLIT.split(" ".join((text or "").split())):
        part = part.strip(" -•·")
        while len(part) > LONG:
            cut = max(part.rfind(", ", 0, LONG), part.rfind(" ", 0, LONG))
            cut = cut if cut > LONG // 2 else LONG
            out.append(part[:cut].strip(" ,"))
            part = part[cut:].strip(" ,")
        if len(part) >= 3:
            out.append(part)
    return out


def trim(text: str, cap: int = CAP) -> list[str]:
    """The sentences worth reading, in their original order."""
    parts = sentences(text)
    facts = [i for i, p in enumerate(parts) if FACTS.search(p)]
    chosen_facts = set(facts)
    rest = [i for i, p in enumerate(parts) if i not in chosen_facts and KEEP.search(p) and not DROP.search(p)]
    chosen, size = [], 0
    for i in facts + rest:
        if size + len(parts[i]) > cap:
            continue
        chosen.append(i)
        size += len(parts[i]) + 1
    return [parts[i] for i in sorted(chosen)]


def text_hash(sents: list[str]) -> str:
    return hashlib.sha1("\n".join(sents).encode()).hexdigest()[:12]



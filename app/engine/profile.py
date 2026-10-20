"""Skills-profile intake: text from a CV (PDF / TXT) and rule-based skill detection with evidence.
The language model, when available, refines this; detected skills are always shown for the user to confirm."""
import io
import re

from pypdf import PdfReader

from ..catalog import Catalog

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 20000
SENIORITY = re.compile(r"\b(advanced|expert|senior|lead|supervis\w*|manag\w*|\d+\s*(\+\s*)?years?)\b", re.IGNORECASE)
SPLIT = re.compile(r"[\r\n]+|(?<=[.;])\s+")


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large (max 4 MB).")
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
    elif name.endswith((".txt", ".md")) or not name:
        text = data.decode("utf-8", errors="replace")
    else:
        raise ValueError("Please upload a PDF or a plain-text file.")
    return text[:MAX_TEXT_CHARS]


def detect_skills(catalog: Catalog, text: str) -> list[dict]:
    lines = [line.strip() for line in SPLIT.split(text) if line.strip()]
    found = []
    for sid, patterns in catalog.alias_patterns.items():
        evidence, matched = [], set()
        for line in lines:
            for pattern in patterns:
                m = pattern.search(line)
                if m:
                    evidence.append(line[:180])
                    matched.add(m.group(0).lower())
                    break
        if evidence:
            level = 1 + (len(evidence) >= 2) + any(SENIORITY.search(e) for e in evidence)
            found.append({"id": sid, "level": min(level, 3), "evidence": evidence[:2],
                          "matched": sorted(matched)[:4], "source": "rules"})
    return sorted(found, key=lambda x: (-x["level"], x["id"]))

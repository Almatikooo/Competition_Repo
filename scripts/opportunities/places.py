"""Location strings -> ISO 3166 country codes, using the GeoNames gazetteer (CC BY 4.0, cached in data/cache).

Job boards write locations every way imaginable ("San Francisco, CA", "Remote (EU)", "KL / Singapore",
"Berlin, Germany"). We look for country names and aliases, then major cities, then "City, ST" US/Canada/
Australia state codes, and separately detect whether a post is remote and from where it can be done.
"""
import io
import re
import zipfile
from functools import lru_cache
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data/cache/opportunities/geonames"
GEONAMES = "https://download.geonames.org/export/dump/"
MIN_CITY_POP = 150_000
# English words that are also city names; matching them would mislabel job text
CITY_STOP = {"reading", "mobile", "nice", "split", "bath", "sale", "orange", "victoria", "hamilton", "santa", "march", "batman", "of",
             "deal", "university", "independence", "concord", "salem", "eugene", "gary", "irving", "mission", "york", "kent", "surrey",
             "essex", "cork", "zug", "anchorage", "moore", "lafayette", "columbia", "aurora", "spring", "pasadena", "plano", "providence",
             "charleston", "georgetown", "kingston", "richmond", "jackson", "madison", "lincoln", "arlington", "frisco", "buffalo",
             "phoenix", "sandy", "garden grove", "garland", "kansas city", "san jose", "córdoba", "cordoba", "mérida", "merida",
             "valencia", "santiago", "san josé", "guadalupe", "trinidad", "la paz", "victoria", "london", "paris", "berlin", "delhi"}
CITY_KEEP = {"london": "GB", "paris": "FR", "berlin": "DE", "delhi": "IN", "new delhi": "IN", "san jose": "US", "kansas city": "US",
             "phoenix": "US", "valencia": "ES", "santiago": "CL", "córdoba": "AR", "victoria": "CA", "richmond": "US", "madison": "US",
             "arlington": "US", "providence": "US", "york": "GB"}
EXTRA_CITIES = {"nyc": "US", "sf": "US", "bay area": "US", "silicon valley": "US", "palo alto": "US", "mountain view": "US",
                "menlo park": "US", "sunnyvale": "US", "redmond": "US", "cupertino": "US", "boulder": "US", "cambridge, ma": "US",
                "washington, dc": "US", "washington dc": "US", "dc": "US", "kl": "MY", "klcc": "MY", "petaling jaya": "MY",
                "cyberjaya": "MY", "penang": "MY", "johor bahru": "MY", "bangsar": "MY", "putrajaya": "MY", "selangor": "MY",
                "bengaluru": "IN", "bangalore": "IN", "gurgaon": "IN", "gurugram": "IN", "noida": "IN", "hyderabad": "IN",
                "hong kong": "HK", "macau": "MO", "singapore": "SG", "luxembourg": "LU", "monaco": "MC", "dubai": "AE",
                "abu dhabi": "AE", "tel aviv": "IL", "zurich": "CH", "zürich": "CH", "geneva": "CH", "munich": "DE", "münchen": "DE",
                "cologne": "DE", "köln": "DE", "frankfurt": "DE", "düsseldorf": "DE", "the hague": "NL", "eindhoven": "NL",
                "lisbon": "PT", "porto": "PT", "dublin": "IE", "edinburgh": "GB", "manchester": "GB", "bristol": "GB",
                "toronto": "CA", "vancouver": "CA", "montreal": "CA", "montréal": "CA", "waterloo": "CA", "ottawa": "CA",
                "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "perth": "AU", "auckland": "NZ", "wellington": "NZ",
                "são paulo": "BR", "sao paulo": "BR", "mexico city": "MX", "cdmx": "MX", "bogotá": "CO", "bogota": "CO",
                "buenos aires": "AR", "tokyo": "JP", "osaka": "JP", "seoul": "KR", "taipei": "TW", "shanghai": "CN",
                "beijing": "CN", "shenzhen": "CN", "jakarta": "ID", "manila": "PH", "makati": "PH", "bangkok": "TH",
                "ho chi minh city": "VN", "hanoi": "VN", "lagos": "NG", "nairobi": "KE", "cape town": "ZA", "johannesburg": "ZA",
                "cairo": "EG", "riyadh": "SA", "doha": "QA", "istanbul": "TR", "warsaw": "PL", "kraków": "PL", "krakow": "PL",
                "prague": "CZ", "budapest": "HU", "bucharest": "RO", "athens": "GR", "barcelona": "ES", "madrid": "ES",
                "milan": "IT", "rome": "IT", "stockholm": "SE", "copenhagen": "DK", "oslo": "NO", "helsinki": "FI",
                "amsterdam": "NL", "brussels": "BE", "vienna": "AT", "tallinn": "EE", "vilnius": "LT", "riga": "LV", "kyiv": "UA"}
COUNTRY_ALIASES = {"usa": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US", "america": "US", "us": "US",
                   "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "northern ireland": "GB",
                   "great britain": "GB", "britain": "GB", "uae": "AE", "emirates": "AE", "south korea": "KR", "korea": "KR",
                   "republic of korea": "KR", "czech republic": "CZ", "czechia": "CZ", "russia": "RU", "vietnam": "VN",
                   "viet nam": "VN", "turkey": "TR", "türkiye": "TR", "turkiye": "TR", "the netherlands": "NL", "holland": "NL",
                   "deutschland": "DE", "méxico": "MX", "brasil": "BR", "hong kong sar": "HK", "taiwan": "TW", "macao": "MO",
                   "ivory coast": "CI", "côte d'ivoire": "CI", "laos": "LA", "syria": "SY", "iran": "IR", "bolivia": "BO",
                   "venezuela": "VE", "tanzania": "TZ", "moldova": "MD", "brunei": "BN", "palestine": "PS", "kosovo": "XK"}
US_STATES = {"AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
             "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
             "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine",
             "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi", "MO": "missouri",
             "MT": "montana", "NE": "nebraska", "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico",
             "NY": "new york", "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
             "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee",
             "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
             "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia"}
CA_PROVINCES = {"ON": "ontario", "QC": "quebec", "BC": "british columbia", "AB": "alberta", "MB": "manitoba", "SK": "saskatchewan",
                "NS": "nova scotia", "NB": "new brunswick", "NL": "newfoundland", "PE": "prince edward island"}
AU_STATES = {"NSW": "new south wales", "VIC": "victoria", "QLD": "queensland", "TAS": "tasmania", "ACT": "australian capital territory"}
# "Remote (Europe)" and friends: where a remote job can be done from
EU = "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
REGIONS = {
    "europe": EU + ["GB", "CH", "NO", "IS", "UA", "RS", "BA", "AL", "MK", "ME", "MD", "TR"], "eu": EU, "eea": EU + ["NO", "IS", "LI"],
    "emea": EU + ["GB", "CH", "NO", "AE", "SA", "IL", "EG", "ZA", "NG", "KE", "MA", "TR"], "uk/eu": EU + ["GB"],
    "apac": ["AU", "NZ", "SG", "MY", "ID", "PH", "TH", "VN", "JP", "KR", "IN", "HK", "TW", "CN"], "asia": ["SG", "MY", "ID", "PH", "TH", "VN", "JP", "KR", "IN", "HK", "TW", "CN", "BD", "PK", "LK"],
    "southeast asia": ["SG", "MY", "ID", "PH", "TH", "VN", "KH", "LA", "MM", "BN"], "sea": ["SG", "MY", "ID", "PH", "TH", "VN"],
    "latam": ["MX", "BR", "AR", "CO", "CL", "PE", "UY", "EC", "CR", "GT", "BO", "PY", "DO", "PA", "VE", "SV", "HN", "NI"],
    "latin america": ["MX", "BR", "AR", "CO", "CL", "PE", "UY", "EC", "CR"], "americas": ["US", "CA", "MX", "BR", "AR", "CO", "CL", "PE"],
    "north america": ["US", "CA"], "africa": ["NG", "KE", "ZA", "EG", "GH", "MA", "RW", "UG", "TZ", "ET"], "middle east": ["AE", "SA", "QA", "IL", "JO", "BH", "KW", "OM"],
}
REMOTE = re.compile(r"\bremote\b|work from (home|anywhere)|\bwfh\b|\banywhere\b|\bdistributed\b|\btelecommut|\bfully remote\b", re.I)
WORLDWIDE = re.compile(r"\bworld ?wide\b|\banywhere\b|\bglobal(ly)?\b|\bany (country|location|timezone)\b|\binternational\b", re.I)


def download() -> None:
    """Fetch the two GeoNames files once (the cache folder is not in git)."""
    if (GEO / "countryInfo.txt").exists() and (GEO / "cities15000.txt").exists():
        return
    from .fetch import USER_AGENT
    GEO.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        info = client.get(GEONAMES + "countryInfo.txt")
        info.raise_for_status()
        (GEO / "countryInfo.txt").write_bytes(info.content)
        cities = client.get(GEONAMES + "cities15000.zip")
        cities.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(cities.content)) as archive:
            (GEO / "cities15000.txt").write_bytes(archive.read("cities15000.txt"))


@lru_cache(maxsize=1)
def gazetteer() -> dict:
    download()
    names: dict[str, str] = {}
    country_names: dict[str, str] = {}
    for line in (GEO / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cols = line.split("\t")
        iso, name = cols[0], cols[4]
        country_names[iso] = name
        names[name.lower()] = iso
    names.update(COUNTRY_ALIASES)
    cities: dict[str, tuple[str, int]] = {}
    with open(GEO / "cities15000.txt", encoding="utf-8") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            pop = int(cols[14] or 0)
            if pop < MIN_CITY_POP:
                continue
            for name in {cols[1].lower(), cols[2].lower()}:
                if len(name) < 3 or name in CITY_STOP:
                    continue
                if name not in cities or cities[name][1] < pop:
                    cities[name] = (cols[8], pop)
    city_names = {k: v[0] for k, v in cities.items()}
    city_names.update(CITY_KEEP)
    city_names.update(EXTRA_CITIES)
    for code, state in US_STATES.items():
        city_names.setdefault(state, "US")
    for code, prov in CA_PROVINCES.items():
        city_names.setdefault(prov, "CA")
    for code, st in AU_STATES.items():
        city_names.setdefault(st, "AU")

    def alternation(keys):
        return re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True)) + r")(?![\w-])", re.I)
    return {"country_names": country_names, "countries": names, "cities": city_names,
            "country_re": alternation(names), "city_re": alternation(city_names),
            "state_re": re.compile(r",\s*(" + "|".join(list(US_STATES) + list(CA_PROVINCES) + list(AU_STATES)) + r")\b"),
            "region_re": alternation(REGIONS)}


def countries_in(text: str) -> list[str]:
    """Countries named or implied (by a city or a 'City, ST' state code) in a location string, in order of appearance."""
    if not text:
        return []
    g = gazetteer()
    found: list[tuple[int, str]] = []
    for m in g["country_re"].finditer(text):
        word = m.group(1)
        if word.lower() == "us" and word != "US":   # 'us' the pronoun
            continue
        found.append((m.start(), g["countries"][word.lower()]))
    for m in g["city_re"].finditer(text):
        found.append((m.start(), g["cities"][m.group(1).lower()]))
    for m in g["state_re"].finditer(text):
        code = m.group(1)
        found.append((m.start(), "US" if code in US_STATES else "CA" if code in CA_PROVINCES else "AU"))
    out: list[str] = []
    for _, iso in sorted(found):
        if iso not in out:
            out.append(iso)
    return out


def remote_scope(text: str) -> list[str] | str | None:
    """None if not remote; 'WORLD' only if the post says it can be done from anywhere; the countries it can be done
    from if it names them; 'UNSPECIFIED' for a bare 'Remote' (employers usually mean their own countries)."""
    if not text or not REMOTE.search(text):
        return None
    g = gazetteer()
    if WORLDWIDE.search(text):
        return "WORLD"
    scope: list[str] = []
    for m in g["region_re"].finditer(text):
        for iso in REGIONS[m.group(1).lower()]:
            if iso not in scope:
                scope.append(iso)
    for iso in countries_in(text):
        if iso not in scope:
            scope.append(iso)
    return scope or "UNSPECIFIED"

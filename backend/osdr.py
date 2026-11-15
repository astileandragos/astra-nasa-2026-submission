"""Search NASA's Open Science Data Repository (OSDR) for related studies. Read only, label "external".

OSDR (https://osdr.nasa.gov) hosts the data of space biology and human research studies. Its public search API
(https://osdr.nasa.gov/osdr/data/search) answers a keyword search with study metadata. What it finds is LITERATURE
AND DATASET METADATA: titles, organisms, factors, links. It is never mixed with the sensor measurements and nothing
found here is compared with them. The OSDR biology studies are mostly omics, imaging and behaviour data; there is no
wearable heart rate, SpO2 or accelerometer time series in them (searches for those terms return nothing).
"""
import itertools
import json
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SEARCH_URL = "https://osdr.nasa.gov/osdr/data/search"
STUDY_URL = "https://osdr.nasa.gov/bio/repo/data/studies/{accession}"
TYPES = ("cgene", "alsda")            # NASA GeneLab (cgene) and the Ames Life Sciences Data Archive (alsda)
TYPE_NAMES = {"cgene": "NASA GeneLab", "alsda": "NASA Ames Life Sciences Data Archive"}
MAX_QUERY = 100
SIZES = (1, 20)
CACHE_TTL_S = 600
TIMEOUT_S = 8
DESCRIPTION_CHARS = 320
ACCESSION_RE = re.compile(r"^OSD-\d{1,5}$")

_cache = {}
_lock = threading.Lock()


def clean_query(text):
    """A search term of 2 to 100 characters: letters, digits, spaces and . , - _ + ' only. Raises ValueError."""
    if not isinstance(text, str):
        raise ValueError("q must be text")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 2 or len(text) > MAX_QUERY:
        raise ValueError(f"q must be between 2 and {MAX_QUERY} characters")
    if not re.fullmatch(r"[\w .,\-+']+", text):
        raise ValueError("q may only contain letters, digits, spaces and . , - _ + '")
    return text


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ASTRA-educational-prototype"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:
        return json.loads(answer.read().decode("utf-8"))


def _released(value):
    """OSDR uses 0 (1970-01-01) for 'no date'; show that as None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 86400:
        return None
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d")


def _text(value, limit=None):
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return None
    return value if limit is None or len(value) <= limit else value[:limit].rstrip() + "..."


def parse_hit(hit, data_type):
    source = hit.get("_source") if isinstance(hit, dict) else None
    if not isinstance(source, dict):
        return None
    accession = source.get("Accession") or source.get("Study Identifier")
    if not isinstance(accession, str) or not ACCESSION_RE.match(accession):
        return None
    return {"accession": accession, "title": _text(source.get("Study Title")) or accession,
            "organism": _text(source.get("organism") or source.get("Organism")),
            "material": _text(source.get("Material Type")),
            "factors": _text(source.get("Study Factor Type")), "released": _released(source.get("Study Public Release Date")),
            "summary": _text(source.get("Study Description"), DESCRIPTION_CHARS),
            "data_type": data_type, "data_type_name": TYPE_NAMES[data_type],
            "url": STUDY_URL.format(accession=accession), "label": "external"}


def search(query, data_type="all", size=10, fetch=None, now=None):
    """Search OSDR. Returns {"query", "type", "total", "results", ...}. Raises ValueError or OSError."""
    query = clean_query(query)
    if data_type not in (*TYPES, "all"):
        raise ValueError(f"type must be one of {[*TYPES, 'all']}")
    if isinstance(size, bool) or not isinstance(size, int) or not SIZES[0] <= size <= SIZES[1]:
        raise ValueError(f"size must be a whole number between {SIZES[0]} and {SIZES[1]}")
    now = now or datetime.now(timezone.utc)
    key = (query.lower(), data_type, size)
    with _lock:
        cached = _cache.get(key)
    if cached and (now - cached[0]).total_seconds() < CACHE_TTL_S:
        return {**cached[1], "cached": True}
    fetch = fetch or fetch_json
    per_type, total = [], 0
    for kind in (TYPES if data_type == "all" else (data_type,)):
        url = SEARCH_URL + "?" + urllib.parse.urlencode({"term": query, "from": 0, "size": size, "type": kind})
        answer = fetch(url)
        hits = (answer.get("hits") or {}) if isinstance(answer, dict) else {}
        count = hits.get("total")
        total += count if isinstance(count, int) else 0
        per_type.append([item for item in (parse_hit(hit, kind) for hit in hits.get("hits") or []) if item])
    results = []                                           # alternate between the two archives so neither one hides the other
    for item in (x for pair in itertools.zip_longest(*per_type) for x in pair if x):
        if all(item["accession"] != r["accession"] for r in results):
            results.append(item)
    payload = {"query": query, "type": data_type, "total": total, "shown": len(results[:size]), "results": results[:size],
               "source": "external", "source_name": "NASA Open Science Data Repository (OSDR)",
               "note": ("Study metadata from NASA OSDR. These are space biology and human research studies (mostly omics, "
                        "imaging and behaviour). They are not live telemetry, not ASTRA data and not comparable with the "
                        "sensor readings."),
               "cached": False}
    with _lock:
        _cache[key] = (now, payload)
        if len(_cache) > 50:
            _cache.pop(next(iter(_cache)))
    return payload


def clear_cache():
    with _lock:
        _cache.clear()

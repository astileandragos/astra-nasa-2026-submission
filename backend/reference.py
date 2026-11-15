"""Curated external references (published papers and public datasets) for the NASA reference panel.

They live in data/reference.json, apart from the sensor measurements, so external data can never be
mixed with live_hardware, simulated or self_reported rows. Only facts that were read from the source
belong in the file; numbers that were not extracted stay out. Each item names what it cannot be
compared with.
"""
import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "reference.json"
KINDS = {"literature", "dataset"}
STATUSES = {"needs_review", "reviewed"}
TEXT_FIELDS = ("id", "title", "kind", "mission", "source_url", "access", "retrieved", "status")
LIST_FIELDS = ("statements", "cannot_be_compared")
TOPICS = {"radiation", "cardiovascular", "sleep_activity", "isolation_behavior", "human_spaceflight", "countermeasures"}


def validate_item(item):
    if not isinstance(item, dict):
        raise ValueError("a reference item must be an object")
    for field in TEXT_FIELDS:
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"reference item needs a text field '{field}'")
    for field in LIST_FIELDS:
        value = item.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
            raise ValueError(f"reference item '{item.get('id')}' needs a non-empty list of text in '{field}'")
    topics = item.get("topics", [])
    if not isinstance(topics, list) or not all(isinstance(x, str) and x in TOPICS for x in topics):
        raise ValueError(f"reference item '{item['id']}': topics must be a list taken from {sorted(TOPICS)}")
    if item["kind"] not in KINDS:
        raise ValueError(f"reference item '{item['id']}': kind must be one of {sorted(KINDS)}")
    if item["status"] not in STATUSES:
        raise ValueError(f"reference item '{item['id']}': status must be one of {sorted(STATUSES)}")
    if not item["source_url"].startswith("https://"):
        raise ValueError(f"reference item '{item['id']}': source_url must be an https link")


def load(path=DEFAULT_PATH):
    """Read, validate and return the reference items. Raises OSError or ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("reference file must look like {\"items\": [...]}")
    seen = set()
    for item in items:
        validate_item(item)
        if item["id"] in seen:
            raise ValueError(f"duplicate reference id '{item['id']}'")
        seen.add(item["id"])
    return [{**item, "topics": item.get("topics", []), "label": "external",
             "note": "Extracted from the literature or a public dataset page. Not live telemetry and not ASTRA data."}
            for item in items]

"""Tests for logging, safer errors, /api/status, CSV export and /api/reference."""
import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timedelta

import pytest

import reference
from app import create_app

GOOD = {"device_id": "ASTRA-01", "heart_rate_bpm": 72, "spo2_percent": 98, "signal_quality": "good",
        "source": "simulated"}


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "t.db"
    return create_app(db, log_path=tmp_path / "astra.log").test_client(), db, tmp_path


def add(db, moment, hr=70, source="simulated", quality="good", device="T"):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, signal_quality, source) "
                  "VALUES (?,?,?,?,?)", (moment.isoformat(timespec="seconds"), device, hr, quality, source))


# ---- logging and safer errors ----
def test_rejected_request_is_logged_without_the_body(env, caplog):
    c, _, tmp = env
    with caplog.at_level(logging.WARNING):
        r = c.post("/api/journal", json={"date": "2026-11-14", "mood": 0, "note": "private diary text"})
    assert r.status_code == 400
    assert "mood" in caplog.text and "private diary text" not in caplog.text


def test_log_file_is_written(env):
    c, _, tmp = env
    c.post("/api/measurements", json={**GOOD, "heart_rate_bpm": 0})
    for handler in logging.getLogger("app").handlers:
        handler.flush()
    assert "heart_rate_bpm" in (tmp / "astra.log").read_text(encoding="utf-8")


def test_unexpected_error_gives_json_500_and_server_keeps_working(env, monkeypatch):
    c, _, _ = env
    import app as app_module

    def boom(*a, **k):
        raise RuntimeError("disk exploded")
    monkeypatch.setattr(app_module.analysis, "quality", boom)
    r = c.get("/api/quality")
    assert r.status_code == 500 and r.get_json() == {"status": "error", "message": "internal server error"}
    assert c.get("/api/health").status_code == 200


def test_oversized_body_rejected(env):
    c, _, _ = env
    r = c.post("/api/measurements", data="x" * 70_000, content_type="application/json")
    assert r.status_code == 413 and r.get_json()["status"] == "error"


def test_database_uses_wal(env):
    _, db, _ = env
    assert sqlite3.connect(db).execute("PRAGMA journal_mode").fetchone()[0] == "wal"


# ---- /api/status ----
def test_status_empty(env):
    c, _, _ = env
    body = c.get("/api/status?source=live_hardware").get_json()
    assert body["total"] == 0 and body["last_received_at"] is None and body["stale"] is True
    assert body["seconds_since_last"] is None and body["median_interval_seconds"] is None


def test_status_fresh_and_interval(env):
    c, db, _ = env
    now = datetime.now().astimezone()
    for i in range(5):
        add(db, now - timedelta(seconds=2 * (4 - i)))     # one reading every 2 s, the last one now
    body = c.get("/api/status?source=simulated").get_json()
    assert body["total"] == 5 and body["stale"] is False and body["median_interval_seconds"] == 2.0
    assert body["seconds_since_last"] <= 2 and body["latest_signal_quality"] == "good"


def test_status_stale_and_per_source(env):
    c, db, _ = env
    add(db, datetime.now().astimezone() - timedelta(minutes=5), source="simulated")
    assert c.get("/api/status?source=simulated").get_json()["stale"] is True
    assert c.get("/api/status?source=simulated&stale_after=3600").get_json()["stale"] is False
    assert c.get("/api/status?source=live_hardware").get_json()["total"] == 0     # sources are not mixed
    assert c.get("/api/status?stale_after=0").status_code == 400


# ---- CSV export ----
def rows_of(response):
    return list(csv.reader(io.StringIO(response.get_data(as_text=True))))


def test_csv_measurements_missing_is_empty_not_zero(env):
    c, db, _ = env
    now = datetime.now().astimezone()
    add(db, now, hr=71)
    add(db, now + timedelta(seconds=1), hr=None, quality="no_finger")
    add(db, now, hr=99, source="live_hardware")                # another source must not appear
    r = c.get("/api/export.csv?source=simulated&days=1")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "attachment" in r.headers["Content-Disposition"] and ".csv" in r.headers["Content-Disposition"]
    rows = rows_of(r)
    header = rows[0]
    assert header[:3] == ["id", "received_at", "device_id"] and len(rows) == 3
    hr_index = header.index("heart_rate_bpm")
    assert [row[hr_index] for row in rows[1:]] == ["71.0", ""]
    assert {row[header.index("source")] for row in rows[1:]} == {"simulated"}


def test_csv_journal_and_formula_protection(env):
    c, _, _ = env
    c.post("/api/journal", json={"date": datetime.now().date().isoformat(), "mood": 3, "note": "=HYPERLINK(1)"})
    rows = rows_of(c.get("/api/export.csv?kind=journal&source=live_hardware&days=1"))
    assert rows[0][0] == "date" and len(rows) == 2
    note = rows[1][rows[0].index("note")]
    assert note.startswith("'=")                               # a spreadsheet will not run it as a formula
    assert rows[1][rows[0].index("sleep_hours")] == ""        # skipped answer: empty, never 0


def test_csv_bad_arguments(env):
    c, _, _ = env
    assert c.get("/api/export.csv?kind=secrets").status_code == 400
    assert c.get("/api/export.csv?days=0").status_code == 400
    assert c.get("/api/export.csv?source=bad").status_code == 400


# ---- reference data ----
def test_real_reference_file_is_valid_and_labelled_external(env):
    c, _, _ = env
    body = c.get("/api/reference").get_json()
    assert body["count"] >= 3 and body["source"] == "external"
    for item in body["items"]:
        assert item["label"] == "external" and item["source_url"].startswith("https://")
        assert item["cannot_be_compared"] and item["status"] in ("needs_review", "reviewed")
    ids = {i["id"] for i in body["items"]}
    assert "flight-crew-physiological-data" in ids
    pilots = next(i for i in body["items"] if i["id"] == "flight-crew-physiological-data")
    assert "not astronaut" in " ".join(pilots["cannot_be_compared"]).lower()


def test_reference_does_not_touch_measurements(env):
    c, _, _ = env
    c.get("/api/reference")
    assert c.get("/api/measurements").get_json() == []


@pytest.mark.parametrize("change", [
    {"kind": "numbers"}, {"status": "ok"}, {"source_url": "http://x.org"}, {"statements": []}, {"title": ""},
    {"cannot_be_compared": ["ok", 3]},
])
def test_reference_validation_rejects_bad_items(tmp_path, change):
    good = json.loads(reference.DEFAULT_PATH.read_text(encoding="utf-8"))["items"][0]
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({"items": [{**good, **change}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        reference.load(path)


def test_reference_duplicate_ids_and_broken_file(tmp_path):
    good = json.loads(reference.DEFAULT_PATH.read_text(encoding="utf-8"))["items"][0]
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({"items": [good, good]}), encoding="utf-8")
    with pytest.raises(ValueError):
        reference.load(path)
    c = create_app(tmp_path / "t.db", reference_path=tmp_path / "missing.json").test_client()
    r = c.get("/api/reference")
    assert r.status_code == 500 and r.get_json()["status"] == "error"

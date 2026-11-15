"""Tests for GET /api/timeline (docs/api_contract.md section 6.11)."""
import sqlite3

import pytest

from app import create_app

DAYS = ["2026-01-%02d" % d for d in range(1, 9)]
TODAY = DAYS[-1]


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "t.db"
    return create_app(db).test_client(), db


def add(db, day, hour, hr, quality="good", source="simulated", acc=(0.0, 0.0, 1.0)):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, "
                  "accel_y_g, accel_z_g, signal_quality, source) VALUES (?,?,?,97,?,?,?,?,?)",
                  (f"{day}T{hour:02d}:00:00+02:00", "T", hr, *acc, quality, source))


def checkin(db, day, source="simulated", sleep=7.0):
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO journal (date, received_at, sleep_hours, mood, source) VALUES (?,?,?,?,?)",
                  (day, f"{day}T20:00:00+02:00", sleep, 4, source))


def fill(db, day, hr, n=24, **kw):
    for i in range(n):
        add(db, day, i, hr + (i % 3) - 1, **kw)


def timeline(c, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return c.get(f"/api/timeline?{q}").get_json()


def test_one_row_per_day_with_nulls_for_gaps(env):
    c, db = env
    add(db, TODAY, 1, 70)
    body = timeline(c, source="simulated", date=TODAY, days=3)
    assert [d["date"] for d in body["per_day"]] == ["2026-01-06", "2026-01-07", "2026-01-08"]
    empty = body["per_day"][0]
    assert empty["readings"] == 0 and empty["heart_rate_bpm"] == {"median": None, "n": 0}
    assert empty["movement_index"] is None and empty["checkin"] is None      # missing is null, never 0
    assert body["baseline"] is None


def test_combines_heart_rate_movement_and_checkin(env):
    c, db = env
    for hr, acc in ((60, (0, 0, 1.0)), (70, (0, 0, 1.5)), (80, (0, 0, 1.0))):
        add(db, TODAY, 5, hr, acc=acc)
    add(db, TODAY, 6, 200, quality="poor")           # poor signal: ignored for heart rate
    checkin(db, TODAY)
    day = timeline(c, source="simulated", date=TODAY, days=1)["per_day"][0]
    assert day["heart_rate_bpm"] == {"median": 70, "n": 3}
    assert day["movement_index"] == pytest.approx(0.125, abs=0.001)     # (0 + 0.5 + 0 + 0) / 4
    assert day["checkin"]["sleep_hours"] == 7 and day["checkin"]["source"] == "simulated" and day["readings"] == 4


def test_sources_not_mixed(env):
    c, db = env
    add(db, TODAY, 1, 70, source="live_hardware")
    checkin(db, TODAY, source="self_reported")
    sim = timeline(c, source="simulated", date=TODAY, days=1)["per_day"][0]
    assert sim["readings"] == 0 and sim["checkin"] is None
    live = timeline(c, source="live_hardware", date=TODAY, days=1)["per_day"][0]
    assert live["readings"] == 1 and live["checkin"]["source"] == "self_reported"


def test_baseline_included_when_ready(env):
    c, db = env
    for d, hr in zip(DAYS[:-1], (64, 65, 66, 67, 68, 66, 66)):
        fill(db, d, hr)
    body = timeline(c, source="simulated", date=TODAY)
    assert body["baseline"]["median"] == 66 and body["baseline"]["days_used"] == 7 and len(body["per_day"]) == 7
    assert set(body["baseline"]) == {"median", "q1", "q3", "days_used"}


@pytest.mark.parametrize("q", ["days=0", "days=31", "source=bad", "date=nope"])
def test_bad_arguments(env, q):
    c, _ = env
    assert c.get(f"/api/timeline?{q}").status_code == 400

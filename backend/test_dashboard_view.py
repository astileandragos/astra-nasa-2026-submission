"""The combined dashboard view: earlier days from the simulated baseline week, today from the live sensor."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from app import create_app


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "d.db"
    return create_app(db).test_client(), db


def day(back):
    return (datetime.now().astimezone() - timedelta(days=back)).date().isoformat()


def add(db, date, hour, hr, source, n=1):
    with sqlite3.connect(db) as c:
        for i in range(n):
            c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, accel_y_g, "
                      "accel_z_g, signal_quality, source) VALUES (?,?,?,97,0,0,1,'good',?)",
                      (f"{date}T{hour:02d}:{i % 60:02d}:00+02:00", "T", hr, source))


def week(db):
    for back in range(7, 0, -1):
        add(db, day(back), 12, 70, "simulated", 30)


def test_baseline_is_simulated_and_today_is_live(env):
    c, db = env
    week(db)
    add(db, day(0), 1, 95, "live_hardware", 30)
    add(db, day(0), 2, 60, "simulated", 30)            # a simulator row of today must not mix with live rows
    rows = c.get("/api/measurements?source=dashboard&limit=500").get_json()
    today = [r for r in rows if r["received_at"][:10] == day(0)]
    assert today and {r["source"] for r in today} == {"live_hardware"}
    assert {r["source"] for r in rows if r["received_at"][:10] < day(0)} == {"simulated"}
    d = c.get("/api/demo/status").get_json()
    assert d["today_source"] == "live_hardware" and d["baseline_days"] == 7 and d["today_readings"] == 30


def test_today_falls_back_to_the_simulator_without_live_readings(env):
    c, db = env
    week(db)
    add(db, day(0), 1, 80, "simulated", 30)
    assert c.get("/api/demo/status").get_json()["today_source"] == "simulated"


def test_live_heart_rate_far_from_the_simulated_week_triggers_a_notification_with_advice(env):
    c, db = env
    week(db)
    add(db, day(0), 1, 95, "live_hardware", 30)
    body = c.get("/api/notifications?source=dashboard").get_json()
    hr = [x for x in body["notifications"] if "heart rate" in x["title"].lower()]
    assert hr and hr[0]["level"] in ("warning", "danger") and hr[0]["advice"]["steps"]
    assert c.get("/api/status?source=dashboard").get_json()["total"] > 0


def test_reset_today_keeps_the_baseline_week(env):
    c, db = env
    week(db)
    add(db, day(0), 1, 95, "live_hardware", 30)
    r = c.post("/api/demo/reset-today").get_json()
    assert r["removed_readings"] == 30
    d = c.get("/api/demo/status").get_json()
    assert d["baseline_days"] == 7 and d["today_readings"] == 0

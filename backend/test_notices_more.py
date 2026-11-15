"""Notifications added on 16 Nov 2026: no movement for an hour, blood oxygen, rest length."""
import sqlite3
from datetime import datetime, timedelta

import pytest

import analysis
import notices
from app import create_app, get_db


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "m.db"
    create_app(path)
    return path


def add(path, day, hour, minute, hr=70, spo2=97, motion=0.0, source="simulated"):
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, accel_y_g, "
                  "accel_z_g, signal_quality, source) VALUES (?,?,?,?,?,0,1,'good',?)",
                  (f"{day}T{hour:02d}:{minute:02d}:00+02:00", "T", hr, spo2, motion, source))


def today():
    return analysis.today_local()


def at(hour, minute=0):
    return datetime.now().astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)


def run(path, now):
    with get_db(path) as conn:
        return {n["id"]: n for n in notices.compute(conn, "simulated", today(), now=now)["notifications"]}


def test_an_hour_without_movement_while_awake_is_a_warning_with_steps(db):
    for m in range(0, 120, 5):                       # 12:00 to 13:55, completely still
        add(db, today(), 12 + m // 60, m % 60)
    n = run(db, at(14, 0))["inactivity"]
    assert n["level"] == "warning" and "No movement for" in n["title"] and n["advice"]["steps"] and n["page"] == "activity.html"


def test_recent_movement_is_ok(db):
    for m in range(0, 120, 5):
        add(db, today(), 12 + m // 60, m % 60, motion=0.6 if m >= 100 else 0.0)
    assert run(db, at(14, 0))["inactivity"]["level"] == "ok"


def test_no_inactivity_notice_at_night_or_without_current_data(db):
    for m in range(0, 120, 5):
        add(db, today(), 12 + m // 60, m % 60)
    assert "inactivity" not in run(db, at(23, 30))     # outside 7:00 to 22:00
    assert "inactivity" not in run(db, at(18, 0))      # the last reading is hours old


def test_low_spo2_today_is_a_warning_in_plain_words(db):
    for back in range(7, 0, -1):
        d = (datetime.now().astimezone() - timedelta(days=back)).date().isoformat()
        for i in range(30):
            add(db, d, 12, i, spo2=97)
    for i in range(30):
        add(db, today(), 1, i, spo2=92)
    n = run(db, at(2, 0))["spo2_vs_baseline"]
    assert n["level"] == "warning" and "Blood oxygen lower than usual" == n["title"] and n["advice"]["steps"]

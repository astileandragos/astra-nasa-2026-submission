"""Tests for GET /api/notifications (docs/api_contract.md section 6.14)."""
import random
import sqlite3
from datetime import datetime, timedelta

import pytest

import seed_demo
from app import create_app, get_db

DAYS = ["2026-01-%02d" % d for d in range(1, 9)]
TODAY = DAYS[-1]
PAGES = {"index.html", "timeline.html", "activity.html", "journal.html", "sensors.html", "radiation.html"}


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "n.db"
    return create_app(db).test_client(), db


def add(db, day, hour, hr, quality="good", source="simulated", stamp=None):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, "
                  "accel_y_g, accel_z_g, signal_quality, source) VALUES (?,?,?,97,0,0,1,?,?)",
                  (stamp or f"{day}T{hour:02d}:00:00+02:00", "T", hr, quality, source))


def fill(db, day, hr, n=24, **kw):
    for i in range(n):
        add(db, day, i, hr + (i % 3) - 1, **kw)


def get(c, **params):
    q = "&".join(f"{k}={v}" for k, v in {"source": "simulated", "date": TODAY, **params}.items())
    return c.get(f"/api/notifications?{q}")


def by_id(body, kind="notifications"):
    return {n["id"]: n for n in body[kind]}


def baseline_then_today(db, today_hr):
    for day in DAYS[:-1][-5:]:
        fill(db, day, 60)
    fill(db, TODAY, today_hr)


# ---------- structure ----------
def test_empty_data_gives_a_valid_answer_without_danger(env):
    c, _ = env
    body = get(c, source="live_hardware", date=datetime.now().astimezone().date().isoformat()).get_json()
    assert body["source"] == "live_hardware" and "not a diagnosis" in body["disclaimer"]
    ids = by_id(body)
    assert ids["connection"]["level"] == "warning" and ids["baseline"]["level"] == "ok"
    assert body["summary"]["danger"] == 0
    assert "s_checkin" in by_id(body, "suggestions")


def test_every_item_has_a_level_a_page_a_target_and_advice(env):
    c, db = env
    baseline_then_today(db, 70)
    body = get(c).get_json()
    for item in body["notifications"] + body["suggestions"]:
        assert item["page"] in PAGES and item["target"] and item["title"]
        assert item["advice"]["meaning"] and isinstance(item["advice"]["steps"], list)
    for item in body["notifications"]:
        assert item["level"] in ("ok", "warning", "danger") and item["message"]
    assert body["suggestions"], "there is always at least one suggestion"
    ids = [n["id"] for n in body["notifications"]] + [s["id"] for s in body["suggestions"]]
    assert len(ids) == len(set(ids))                       # ids are unique, so ?from=<id> is unambiguous


def test_notifications_are_sorted_danger_first(env):
    c, db = env
    baseline_then_today(db, 70)
    levels = [n["level"] for n in get(c).get_json()["notifications"]]
    order = {"danger": 0, "warning": 1, "ok": 2}
    assert levels == sorted(levels, key=order.get)


# ---------- heart rate rule ----------
def test_heart_rate_as_usual_is_green_without_steps(env):
    c, db = env
    baseline_then_today(db, 60)
    item = by_id(get(c).get_json())["hr_vs_baseline"]
    assert item["level"] == "ok" and item["advice"]["steps"] == [] and item["page"] == "timeline.html"


def test_heart_rate_a_little_outside_is_orange_with_steps(env):
    c, db = env
    baseline_then_today(db, 62)          # difference 2 bpm, limit 1 bpm: notable but not more than twice the limit
    item = by_id(get(c).get_json())["hr_vs_baseline"]
    assert item["level"] == "warning" and "higher than usual" in item["title"]
    assert len(item["advice"]["steps"]) >= 3 and "diagnosis" in item["advice"]["meaning"]
    assert not any("medical staff" in s for s in item["advice"]["steps"])


def test_heart_rate_far_outside_is_red_and_says_who_to_tell(env):
    c, db = env
    baseline_then_today(db, 70)
    item = by_id(get(c).get_json())["hr_vs_baseline"]
    assert item["level"] == "danger"
    assert any("crew medical officer" in s and "mission control" in s for s in item["advice"]["steps"])
    assert get(c).get_json()["notifications"][0]["id"] == "hr_vs_baseline"      # red comes first
    assert get(c).get_json()["summary"]["danger"] == 1


def test_a_lower_heart_rate_is_described_as_lower(env):
    c, db = env
    baseline_then_today(db, 50)
    assert "lower than usual" in by_id(get(c).get_json())["hr_vs_baseline"]["title"]


# ---------- connection rule ----------
def stamp_ago(seconds):
    return (datetime.now().astimezone() - timedelta(seconds=seconds)).isoformat(timespec="seconds")


def connection(c, db, seconds):
    add(db, None, None, 60, stamp=stamp_ago(seconds))
    today = datetime.now().astimezone().date().isoformat()
    return by_id(get(c, date=today).get_json())["connection"]


def test_connection_is_green_when_readings_are_fresh(env):
    c, db = env
    item = connection(c, db, 2)
    assert item["level"] == "ok" and item["page"] == "sensors.html"


def test_connection_is_orange_when_readings_are_late(env):
    c, db = env
    assert connection(c, db, 30)["level"] == "warning"


def test_connection_is_red_when_data_stopped(env):
    c, db = env
    item = connection(c, db, 900)
    assert item["level"] == "danger" and item["title"] == "Data stopped"
    assert any("simulator" in s for s in item["advice"]["steps"])          # the steps depend on the source


def test_connection_advice_for_live_hardware_mentions_the_esp32(env):
    c, db = env
    add(db, None, None, 60, source="live_hardware", stamp=stamp_ago(900))
    today = datetime.now().astimezone().date().isoformat()
    item = by_id(get(c, source="live_hardware", date=today).get_json())["connection"]
    assert item["level"] == "danger" and any("ESP32" in s for s in item["advice"]["steps"])


def test_a_past_date_has_no_connection_notification(env):
    c, db = env
    baseline_then_today(db, 60)
    assert "connection" not in by_id(get(c).get_json())


# ---------- signal quality and wear ----------
def test_low_signal_quality_is_orange(env):
    c, db = env
    for i in range(24):
        add(db, TODAY, i, 60 if i % 4 == 0 else None, quality="good" if i % 4 == 0 else "poor")
    item = by_id(get(c).get_json())["signal_quality"]
    assert item["level"] == "warning" and item["page"] == "sensors.html" and len(item["advice"]["steps"]) >= 3


def test_good_signal_quality_is_green(env):
    c, db = env
    fill(db, TODAY, 60)
    assert by_id(get(c).get_json())["signal_quality"]["level"] == "ok"


def test_gaps_in_wear_time_are_orange(env):
    c, db = env
    for i in range(6):
        add(db, TODAY, i, 60)
    item = by_id(get(c).get_json())["wear_time"]
    assert item["level"] == "warning" and item["target"] == "alert-h"


# ---------- rest and suggestions ----------
def test_a_much_later_rest_start_is_an_orange_notification(tmp_path):
    db = tmp_path / "s.db"
    c = create_app(db).test_client()
    with get_db(db) as conn:
        seed_demo.seed(conn, 6, "normal", random.Random(42), late_bed=True)
    item = by_id(c.get("/api/notifications?source=simulated").get_json())["rest_start_vs_usual"]
    assert item["level"] == "warning" and item["page"] == "activity.html" and item["target"] == "rest-h"
    assert "later than usual" in item["message"]


def test_checkin_suggestion_disappears_once_the_checkin_is_saved(env):
    c, db = env
    assert "s_checkin" in by_id(get(c).get_json(), "suggestions")
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO journal (date, received_at, sleep_hours, mood, source) VALUES (?,?,?,?,?)",
                     (TODAY, f"{TODAY}T20:00:00+02:00", 7, 4, "simulated"))
    assert "s_checkin" not in by_id(get(c).get_json(), "suggestions")
    c2 = get(c, source="live_hardware")                                        # a simulated check-in is not live
    assert "s_checkin" in by_id(c2.get_json(), "suggestions")


def test_note_suggestion_appears_only_when_something_needs_attention(env):
    c, db = env
    baseline_then_today(db, 60)
    for i in range(24):                                   # half-hour readings: the whole day has data
        add(db, TODAY, i, 60, stamp=f"{TODAY}T{i:02d}:30:00+02:00")
    assert "s_note" not in by_id(get(c).get_json(), "suggestions")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM measurements WHERE received_at LIKE ?", (f"{TODAY}%",))
    fill(db, TODAY, 70)
    assert "s_note" in by_id(get(c).get_json(), "suggestions")


def test_sources_are_kept_apart(env):
    c, db = env
    baseline_then_today(db, 70)
    assert "hr_vs_baseline" not in by_id(get(c, source="live_hardware").get_json())


def test_input_checks(env):
    c, _ = env
    assert get(c, source="oops").status_code == 400
    assert get(c, date="2026-13-40").status_code == 400
    assert c.get("/api/notifications").get_json()["source"] == "live_hardware"    # default source


def test_every_target_id_exists_on_its_page(tmp_path):
    """A notification must point at a heading that really exists in the page it opens."""
    from pathlib import Path
    pages = Path(__file__).resolve().parent.parent / "frontend"
    db = tmp_path / "t.db"
    c = create_app(db).test_client()
    pairs = set()
    for source in ("live_hardware", "simulated"):                       # empty data, then seeded data
        if source == "simulated":
            with get_db(db) as conn:
                seed_demo.seed(conn, 6, "elevated", random.Random(42), late_bed=True)
        body = c.get(f"/api/notifications?source={source}").get_json()
        pairs |= {(i["page"], i["target"]) for i in body["notifications"] + body["suggestions"]}
    assert len(pairs) >= 6
    for page, target in pairs:
        assert f'id="{target}"' in (pages / page).read_text(encoding="utf-8"), (page, target)

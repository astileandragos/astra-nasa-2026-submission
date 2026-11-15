"""Tests for rest, rest regularity and wear time (docs/api_contract.md sections 6.12 and 6.13)."""
import random
import sqlite3
from datetime import date as date_type
from datetime import timedelta

import pytest

import rest
import seed_demo
from app import create_app, get_db

TODAY = "2026-02-20"
STILL = (0.0, 0.01, 1.0)
MOVING = (0.4, 0.0, 1.2)


def prev(day, n=1):
    return (date_type.fromisoformat(day) - timedelta(days=n)).isoformat()


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "r.db"
    return create_app(db).test_client(), db


def add(db, day, minutes, acc, hr=60, quality="good", source="simulated"):
    stamp = f"{day}T{minutes // 60:02d}:{minutes % 60:02d}:00+02:00"
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, "
                  "accel_y_g, accel_z_g, signal_quality, source) VALUES (?,?,?,97,?,?,?,?,?)",
                  (stamp, "T", hr, *acc, quality, source))


def night(db, day, bed=23.0, wake=6.0, source="simulated", step=15, still_hr=55, moving_at=()):
    """Readings from 18:00 the day before to 12:00 on `day`: still between bed and wake, moving otherwise."""
    before = prev(day)
    for m in range(18 * 60, 24 * 60, step):
        asleep = m >= bed * 60
        add(db, before, m, STILL if asleep else MOVING, still_hr if asleep else 75, source=source)
    for m in range(0, 12 * 60, step):
        asleep = m < wake * 60
        hit = any(a <= m < a + 30 for a in moving_at)
        add(db, day, m, MOVING if (hit or not asleep) else STILL, still_hr if asleep else 75, source=source)


def get_rest(c, **params):
    q = "&".join(f"{k}={v}" for k, v in {"source": "simulated", "date": TODAY, **params}.items())
    return c.get(f"/api/rest?{q}")


# ---------- rest ----------
def test_rest_period_found_from_movement(env):
    c, db = env
    night(db, TODAY, bed=23.0, wake=6.0)
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "ok"
    assert (entry["rest_start"], entry["rest_end"], entry["duration_h"]) == ("23:00", "06:00", 7)
    assert entry["wake_ups"] == 0
    assert entry["coverage"] == 1.0
    assert entry["resting_heart_rate"] == {"median": 55, "n": 28}


def test_one_moving_window_inside_rest_is_a_wake_up(env):
    c, db = env
    night(db, TODAY, bed=23.0, wake=6.0, moving_at=[3 * 60])
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "ok"
    assert entry["wake_ups"] == 1
    assert (entry["rest_start"], entry["rest_end"]) == ("23:00", "06:00")


def test_a_long_interruption_ends_the_rest_period(env):
    c, db = env
    night(db, TODAY, bed=22.0, wake=6.0, moving_at=[0, 30, 60])   # 90 minutes of movement at midnight
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "ok"
    assert (entry["rest_start"], entry["rest_end"]) == ("01:30", "06:00")   # the longer still stretch


def test_no_motion_data_is_insufficient_not_zero(env):
    c, _ = env
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "insufficient_data"
    assert entry["coverage"] == 0.0
    assert entry["rest_start"] is None and entry["duration_h"] is None
    assert entry["wake_ups"] is None and entry["resting_heart_rate"] is None
    assert "motion readings" in entry["reason"]


def test_a_night_with_too_little_data_is_not_used(env):
    c, db = env
    before = prev(TODAY)
    for m in range(18 * 60, 21 * 60, 15):       # only the evening has data
        add(db, before, m, STILL)
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "insufficient_data" and "75%" in entry["reason"]


def test_a_short_still_period_is_not_a_rest_period(env):
    c, db = env
    night(db, TODAY, bed=23.0, wake=1.0)          # 2 hours of stillness is enough
    night(db, prev(TODAY), bed=23.0, wake=0.5)    # 90 minutes is not
    nights = get_rest(c, nights=2).get_json()["per_night"]
    assert nights[1]["status"] == "ok"
    assert nights[0]["status"] == "insufficient_data" and "no still period" in nights[0]["reason"]


def test_readings_without_motion_are_not_counted_as_still(env):
    c, db = env
    before = prev(TODAY)
    with sqlite3.connect(db) as conn:
        for m in range(18 * 60, 24 * 60, 15):
            conn.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, signal_quality, source) "
                         "VALUES (?,?,?,?,?)", (f"{before}T{m // 60:02d}:{m % 60:02d}:00+02:00", "T", 60, "good", "simulated"))
        for m in range(0, 12 * 60, 15):
            conn.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, signal_quality, source) "
                         "VALUES (?,?,?,?,?)", (f"{TODAY}T{m // 60:02d}:{m % 60:02d}:00+02:00", "T", 60, "good", "simulated"))
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["status"] == "insufficient_data" and entry["coverage"] == 0.0   # null motion = no data


def test_poor_signal_heart_rate_is_not_used_for_resting_heart_rate(env):
    c, db = env
    night(db, TODAY, bed=23.0, wake=6.0)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE measurements SET heart_rate_bpm = 200, signal_quality = 'poor' "
                     "WHERE received_at LIKE ? ", (f"{TODAY}T03:%",))
    entry = get_rest(c, nights=1).get_json()["per_night"][0]
    assert entry["resting_heart_rate"]["median"] == 55 and entry["resting_heart_rate"]["n"] == 24


def test_rest_keeps_sources_apart(env):
    c, db = env
    night(db, TODAY, source="live_hardware")
    assert get_rest(c, nights=1).get_json()["per_night"][0]["status"] == "insufficient_data"
    assert get_rest(c, nights=1, source="live_hardware").get_json()["per_night"][0]["status"] == "ok"
    assert c.get("/api/rest?date=" + TODAY).get_json()["source"] == "live_hardware"   # default source


def test_rest_input_checks(env):
    c, _ = env
    assert get_rest(c, nights=0).status_code == 400
    assert get_rest(c, nights=15).status_code == 400
    assert get_rest(c, nights="x").status_code == 400
    assert get_rest(c, source="oops").status_code == 400
    assert c.get("/api/rest?date=2026-13-40").status_code == 400
    body = get_rest(c, nights=3).get_json()
    assert len(body["per_night"]) == 3 and "disclaimer" in body and "not a diagnosis" in body["limits"]


# ---------- regularity ----------
def fill_nights(db, specs):
    for i, (bed, wake) in enumerate(specs):
        night(db, prev(TODAY, len(specs) - 1 - i), bed=bed, wake=wake)


def test_usual_values_need_three_earlier_nights(env):
    c, db = env
    fill_nights(db, [(23.0, 6.0), (23.0, 6.0), (23.0, 6.0)])     # two earlier nights + last night
    assert get_rest(c).get_json()["usual"] is None
    night(db, prev(TODAY, 3), bed=23.0, wake=6.0)
    usual = get_rest(c).get_json()["usual"]
    assert usual["nights_used"] == 3
    assert usual["start_median"] == "23:00" and usual["end_median"] == "06:00"
    assert usual["start_spread_min"] == 0 and usual["start_range_min"] == 0


def test_regularity_spread_is_in_minutes(env):
    c, db = env
    for i, bed in enumerate([22.0, 23.0, 23.5, 23.0]):
        night(db, prev(TODAY, 4 - i), bed=bed, wake=6.0)
    night(db, TODAY, bed=23.0, wake=6.0)
    usual = get_rest(c).get_json()["usual"]
    assert usual["nights_used"] == 4
    assert usual["start_median"] == "23:00"
    assert usual["start_range_min"] == 90
    assert usual["start_spread_min"] > 0


# ---------- observation ----------
def test_observation_flags_a_much_later_rest_start(env):
    c, db = env
    for i, bed in enumerate([23.0, 23.5, 23.0, 23.0, 23.0]):
        night(db, prev(TODAY, 5 - i), bed=bed, wake=6.0 + (bed - 23.0))
    # last night starts at 01:30 (the night window runs on past midnight)
    before = prev(TODAY)
    for m in range(18 * 60, 24 * 60, 15):
        add(db, before, m, MOVING)
    for m in range(0, 12 * 60, 15):
        add(db, TODAY, m, STILL if 90 <= m < 9 * 60 else MOVING)
    items = c.get(f"/api/observation?source=simulated&date={TODAY}").get_json()["observations"]
    obs = next(o for o in items if o["id"] == "rest_start_vs_usual")
    assert obs["level"] == "notable" and "later than usual" in obs["message"]
    assert obs["based_on"]["last_night"] == "01:30" and obs["based_on"]["usual"] == "23:00"
    assert obs["based_on"]["difference_min"] == 150
    assert obs["based_on"]["earlier_nights"] == 5 and "rule" in obs and "suggested_step" in obs


def test_observation_for_a_normal_night_is_information_only(env):
    c, db = env
    for i, bed in enumerate([23.0, 23.5, 23.0, 22.5, 23.0, 23.0]):
        night(db, prev(TODAY, 5 - i), bed=bed, wake=6.0)
    items = c.get(f"/api/observation?source=simulated&date={TODAY}").get_json()["observations"]
    obs = next(o for o in items if o["id"] == "rest_start_vs_usual")
    assert obs["level"] == "info" and "within your usual variation" in obs["message"]
    assert "suggested_step" not in obs


def test_no_rest_observation_without_enough_earlier_nights(env):
    c, db = env
    night(db, prev(TODAY), bed=23.0, wake=6.0)
    night(db, TODAY, bed=23.0, wake=6.0)
    body = c.get(f"/api/observation?source=simulated&date={TODAY}").get_json()
    assert not any(o["id"] == "rest_start_vs_usual" for o in body["observations"])
    assert body["status"] == "insufficient_data"        # the existing behaviour is unchanged


# ---------- wear time ----------
def day_readings(db, day, minutes, source="simulated", **kw):
    for m in minutes:
        add(db, day, m, STILL, source=source, **kw)


def get_wear(c, **params):
    q = "&".join(f"{k}={v}" for k, v in {"source": "simulated", "date": TODAY, **params}.items())
    return c.get(f"/api/wear?{q}")


def test_wear_full_day_is_enough(env):
    c, db = env
    day_readings(db, TODAY, range(0, 24 * 60, 10))
    day = get_wear(c, days=1).get_json()["per_day"][0]
    assert day["coverage"] == 1.0 and day["data_hours"] == 24 and day["enough"] is True
    assert day["heart_rate_hours"] == 24 and day["longest_gap_h"] == pytest.approx(0.2, abs=0.01)


def test_wear_half_day_is_not_enough_and_shows_the_gap(env):
    c, db = env
    day_readings(db, TODAY, range(0, 12 * 60, 10))
    body = get_wear(c, days=1).get_json()
    day = body["per_day"][0]
    assert day["coverage"] == 0.5 and day["data_hours"] == 12 and day["enough"] is False
    assert day["longest_gap_h"] == pytest.approx(12.0, abs=0.2)
    assert body["days_enough"] == 0 and "method" in body and "why" in body


def test_wear_heart_rate_hours_count_only_good_signal(env):
    c, db = env
    day_readings(db, TODAY, range(0, 24 * 60, 10), quality="no_finger", hr=None)
    day = get_wear(c, days=1).get_json()["per_day"][0]
    assert day["data_hours"] == 24 and day["heart_rate_hours"] == 0 and day["coverage"] == 1.0


def test_wear_empty_day_has_a_null_gap(env):
    c, _ = env
    body = get_wear(c, days=3).get_json()
    assert len(body["per_day"]) == 3
    for day in body["per_day"]:
        assert day["coverage"] == 0 and day["longest_gap_h"] is None and day["enough"] is False


def test_wear_today_is_measured_until_now(env):
    _, db = env
    day_readings(db, rest.analysis.today_local(), range(0, 6 * 60, 10))
    with get_db(db) as conn:
        today = rest.wear(conn, "simulated", rest.analysis.today_local(), 1, now_minutes=6 * 60)["per_day"][0]
    assert today["coverage"] == 1.0 and today["enough"] is True      # 6 hours of 6 hours so far


def test_wear_keeps_sources_apart_and_checks_input(env):
    c, db = env
    day_readings(db, TODAY, range(0, 24 * 60, 10), source="live_hardware")
    assert get_wear(c, days=1).get_json()["per_day"][0]["readings"] == 0
    assert get_wear(c, days=1, source="live_hardware").get_json()["per_day"][0]["readings"] == 144
    assert get_wear(c, days=0).status_code == 400
    assert get_wear(c, days=31).status_code == 400
    assert get_wear(c, source="x").status_code == 400


# ---------- seed ----------
def test_seeded_data_gives_rest_nights_that_vary(tmp_path):
    db = tmp_path / "s.db"
    c = create_app(db).test_client()
    with get_db(db) as conn:
        seed_demo.seed(conn, 6, "normal", random.Random(42))
    body = c.get("/api/rest?source=simulated&nights=7").get_json()
    ok = [n for n in body["per_night"] if n["status"] == "ok"]
    assert len(ok) >= 5
    assert len({n["rest_start"] for n in ok}) > 1                    # bedtimes are not all the same
    assert all(5 <= n["duration_h"] <= 10 for n in ok)
    assert body["usual"] is not None
    wear = c.get("/api/wear?source=simulated&days=7").get_json()
    assert wear["per_day"][0]["enough"] is True


def test_seed_late_bed_option_gives_a_notable_observation(tmp_path):
    db = tmp_path / "s.db"
    c = create_app(db).test_client()
    with get_db(db) as conn:
        seed_demo.seed(conn, 6, "normal", random.Random(42), late_bed=True)
    items = c.get("/api/observation?source=simulated").get_json()["observations"]
    obs = next(o for o in items if o["id"] == "rest_start_vs_usual")
    assert obs["level"] == "notable" and "later than usual" in obs["message"]

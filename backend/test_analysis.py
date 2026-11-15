"""Tests for the analysis endpoints and the demo seed (docs/api_contract.md section 6.7)."""
import random
import sqlite3

import pytest

import seed_demo
from app import create_app, get_db

DAYS = ["2026-01-%02d" % d for d in range(1, 9)]   # 01..08; 08 is "today" in these tests
TODAY = DAYS[-1]


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "t.db"
    app = create_app(db)
    return app.test_client(), db


def add(db, day, hour, hr, quality="good", source="simulated", spo2=97, acc=(0.0, 0.0, 1.0), minute=0):
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, "
                  "accel_y_g, accel_z_g, signal_quality, source) VALUES (?,?,?,?,?,?,?,?,?)",
                  (f"{day}T{hour:02d}:{minute:02d}:00+02:00", "T", hr, spo2, *acc, quality, source))


def fill_day(db, day, hr, n=24, source="simulated"):
    for i in range(n):
        add(db, day, i, hr + (i % 3) - 1, source=source)  # median == hr


def journal(db, day, sleep, source="simulated"):
    with sqlite3.connect(db) as c:
        c.execute("INSERT OR REPLACE INTO journal (date, received_at, sleep_hours, source) VALUES (?,?,?,?)",
                  (day, f"{day}T20:00:00+02:00", sleep, source))


def get(c, path, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return c.get(f"{path}?{q}")


# ---- quality and stats ----
def test_quality_counts_and_missing(env):
    c, db = env
    add(db, TODAY, 1, 70)
    add(db, TODAY, 2, 71, quality="poor")
    add(db, TODAY, 3, None, quality="no_finger", spo2=None)
    body = get(c, "/api/quality", source="simulated", date=TODAY, days=3).get_json()
    assert body["total"] == 3 and body["signal_quality"]["good"] == 1 and body["signal_quality"]["poor"] == 1
    assert body["missing"]["heart_rate_bpm"] == 1 and body["good_share"] == 0.333
    assert [d["date"] for d in body["per_day"]] == ["2026-01-06", "2026-01-07", "2026-01-08"]
    assert body["per_day"][0]["total"] == 0


def test_quality_empty_is_null_share(env):
    c, _ = env
    body = get(c, "/api/quality", date=TODAY).get_json()
    assert body["total"] == 0 and body["good_share"] is None and body["source"] == "live_hardware"


def test_stats_use_only_good_values_and_keep_empty_days(env):
    c, db = env
    for hr in (60, 70, 80):
        add(db, TODAY, 5, hr)
    add(db, TODAY, 6, 200, quality="poor")        # poor signal: ignored
    add(db, TODAY, 7, None, quality="good")       # null: ignored, never counted as 0
    body = get(c, "/api/stats/daily", source="simulated", date=TODAY, days=2).get_json()
    hr = body["per_day"][1]["heart_rate_bpm"]
    assert (hr["min"], hr["max"], hr["avg"], hr["median"], hr["n"]) == (60, 80, 70, 70, 3)
    assert body["per_day"][0]["heart_rate_bpm"] == {"min": None, "max": None, "avg": None, "median": None, "n": 0}


def test_sources_are_never_mixed(env):
    c, db = env
    add(db, TODAY, 1, 70, source="live_hardware")
    add(db, TODAY, 2, 90, source="simulated")
    live = get(c, "/api/quality", source="live_hardware", date=TODAY, days=1).get_json()
    sim = get(c, "/api/stats/daily", source="simulated", date=TODAY, days=1).get_json()
    assert live["total"] == 1 and sim["per_day"][0]["heart_rate_bpm"]["max"] == 90


# ---- baseline ----
def test_baseline_not_ready_with_too_little_data(env):
    c, db = env
    fill_day(db, "2026-01-07", 66)
    fill_day(db, "2026-01-06", 66, n=5)            # too few readings: day does not count
    body = get(c, "/api/baseline", source="simulated", date=TODAY).get_json()
    assert body["ready"] is False and body["heart_rate_bpm"] is None and "not enough data" in body["reason"]
    assert body["days_used"] == 1 and "_usable_days" not in body


def test_baseline_ready_excludes_today(env):
    c, db = env
    for d, hr in zip(DAYS[:-1], (64, 65, 66, 67, 68, 66, 66)):
        fill_day(db, d, hr)
    fill_day(db, TODAY, 100)                         # today must not leak into its own baseline
    journal(db, "2026-01-05", 7.0)
    journal(db, "2026-01-06", 7.5)
    journal(db, "2026-01-07", 6.5)
    body = get(c, "/api/baseline", source="simulated", date=TODAY).get_json()
    assert body["ready"] and body["days_used"] == 7 and body["heart_rate_bpm"]["median"] == 66
    assert len(body["heart_rate_bpm"]["daily_medians"]) == 7
    assert body["sleep_hours"] == {"mean": 7, "n": 3}


# ---- observation ----
def baseline_days(db, medians=(65, 66, 67, 66, 65, 67)):
    for d, hr in zip(DAYS[:-1], medians):
        fill_day(db, d, hr)


def test_observation_notable_higher(env):
    c, db = env
    baseline_days(db)
    fill_day(db, TODAY, 80)
    body = get(c, "/api/observation", source="simulated", date=TODAY).get_json()
    obs = body["observations"][0]
    assert body["status"] == "ok" and obs["id"] == "hr_vs_baseline" and obs["level"] == "notable"
    assert "higher" in obs["message"] and obs["based_on"]["today_median"] == 80
    assert obs["based_on"]["baseline_median"] == 66 and obs["based_on"]["period"]["from"] == "2026-01-01"
    assert obs["rule"] and obs["suggested_step"] and "diagnosis" in body["disclaimer"]


def test_observation_within_usual_variation(env):
    c, db = env
    baseline_days(db)
    fill_day(db, TODAY, 66)
    obs = get(c, "/api/observation", source="simulated", date=TODAY).get_json()["observations"][0]
    assert obs["level"] == "info" and "within your usual variation" in obs["message"]
    assert "suggested_step" not in obs


def test_observation_insufficient_data_reasons(env):
    c, db = env
    body = get(c, "/api/observation", source="simulated", date=TODAY).get_json()
    assert body["status"] == "insufficient_data" and body["observations"] == [] and "not enough data" in body["reason"]
    baseline_days(db)
    add(db, TODAY, 1, 70)                              # baseline ok, but only 1 reading today
    body = get(c, "/api/observation", source="simulated", date=TODAY).get_json()
    assert body["status"] == "insufficient_data" and "needed" in body["reason"]


def test_observation_sleep_rule(env):
    c, db = env
    for d, h in zip(DAYS[:-1], (7.0, 7.5, 7.0, 6.5, 7.0, 7.0)):
        journal(db, d, h)
    journal(db, TODAY, 4.0)
    body = get(c, "/api/observation", source="simulated", date=TODAY).get_json()
    obs = body["observations"][0]
    assert obs["id"] == "sleep_vs_average" and obs["level"] == "notable" and "less" in obs["message"]


def test_observation_uses_matching_journal_source(env):
    c, db = env
    for d in DAYS[:-1]:
        journal(db, d, 7.0, source="self_reported")
    journal(db, TODAY, 3.0, source="self_reported")
    sim = get(c, "/api/observation", source="simulated", date=TODAY).get_json()
    assert sim["observations"] == []                    # self-reported entries are not used for simulated data


# ---- activity ----
def test_activity_windows(env):
    c, db = env
    add(db, TODAY, 1, 70, acc=(0.0, 0.0, 1.0), minute=5)
    add(db, TODAY, 1, 70, acc=(0.0, 0.0, 1.0), minute=10)
    add(db, TODAY, 1, 70, acc=(0.6, 0.0, 0.8), minute=40)   # magnitude 1.0 -> index 0
    add(db, TODAY, 2, 70, acc=(0.0, 0.0, 1.5), minute=0)    # index 0.5
    add(db, TODAY, 3, 70, acc=(None, None, None))
    body = get(c, "/api/activity", source="simulated", date=TODAY, window_min=30).get_json()
    w = {x["start"]: x for x in body["windows"]}
    assert len(body["windows"]) == 48 and w["01:00"]["movement_index"] == 0 and w["01:00"]["n"] == 2
    assert w["01:30"]["n"] == 1 and w["02:00"]["movement_index"] == 0.5
    assert w["03:00"]["movement_index"] is None and w["03:00"]["n"] == 0    # null accel: no value, not 0


# ---- arguments and latest ----
@pytest.mark.parametrize("path,q", [
    ("/api/quality", "source=bad"), ("/api/quality", "days=0"), ("/api/quality", "days=31"),
    ("/api/baseline", "date=2026-13-40"), ("/api/baseline", "date=today"), ("/api/activity", "window_min=1"),
    ("/api/observation", "source=nope"), ("/api/stats/daily", "days=abc"),
])
def test_bad_arguments_rejected(env, path, q):
    c, _ = env
    assert c.get(f"{path}?{q}").status_code == 400


def test_latest_by_source(env):
    c, db = env
    add(db, TODAY, 1, 60, source="live_hardware")
    add(db, TODAY, 2, 99, source="external")
    assert c.get("/api/measurements/latest").get_json()["source"] == "external"
    assert c.get("/api/measurements/latest?source=live_hardware").get_json()["heart_rate_bpm"] == 60
    assert c.get("/api/measurements/latest?source=simulated").status_code == 404
    assert c.get("/api/measurements/latest?source=oops").status_code == 400


# ---- seed ----
def test_seed_is_simulated_only_idempotent_and_clearable(tmp_path):
    db = tmp_path / "s.db"
    create_app(db)
    add(db, TODAY, 1, 55, source="live_hardware")             # a real row must survive everything
    add(db, TODAY, 2, 56, source="simulated")                 # another simulated device must survive --clear
    with get_db(db) as conn:
        seed_demo.clear(conn)
        rows, journal_rows = seed_demo.seed(conn, 6, "elevated", random.Random(1))
    assert rows > 500 and journal_rows == 7
    with get_db(db) as conn:
        sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM measurements WHERE device_id='SEED-SIM'")}
        assert sources == {"simulated"}
        assert conn.execute("SELECT COUNT(*) FROM journal WHERE source != 'simulated'").fetchone()[0] == 0
        before = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        seed_demo.clear(conn)
        seed_demo.seed(conn, 6, "elevated", random.Random(1))
        assert conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == before     # no duplicates
        seed_demo.clear(conn)
        left = conn.execute("SELECT source, heart_rate_bpm FROM measurements ORDER BY source").fetchall()
        assert [tuple(r) for r in left] == [("live_hardware", 55), ("simulated", 56)]
        assert conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0] == 0


def test_seeded_data_gives_a_ready_baseline(tmp_path):
    db = tmp_path / "s.db"
    c = create_app(db).test_client()
    with get_db(db) as conn:
        seed_demo.seed(conn, 6, "elevated", random.Random(3))
    body = c.get("/api/baseline?source=simulated").get_json()
    assert body["ready"] and body["days_used"] >= 3 and 55 < body["heart_rate_bpm"]["median"] < 80
    assert c.get("/api/quality?source=live_hardware").get_json()["total"] == 0   # nothing under the live label


# ---- SpO2 against the personal baseline (same rule as heart rate) ----
def spo2_days(db, values, today):
    for d, v in zip(DAYS[:-1], values):
        for i in range(24):
            add(db, d, i, 66, spo2=v)
    for i in range(24):
        add(db, TODAY, i, 66, spo2=today)


def spo2_obs(c):
    items = get(c, "/api/observation", source="simulated", date=TODAY).get_json()["observations"]
    return next((o for o in items if o["id"] == "spo2_vs_baseline"), None)


def test_spo2_notable_lower_than_baseline(env):
    c, db = env
    spo2_days(db, (97, 97, 98, 97, 97, 98), today=93)
    obs = spo2_obs(c)
    assert obs["level"] == "notable" and "lower" in obs["message"] and obs["based_on"]["difference"] < 0
    assert obs["based_on"]["metric"] == "spo2_percent" and obs["rule"]


def test_spo2_within_usual_variation(env):
    c, db = env
    spo2_days(db, (97, 97, 98, 97, 97, 98), today=97)
    obs = spo2_obs(c)
    assert obs["level"] == "info" and "within your usual variation" in obs["message"]


def test_spo2_needs_enough_days_and_readings(env):
    c, db = env
    for d in DAYS[:2]:                                   # only 2 earlier days: no baseline
        for i in range(24):
            add(db, d, i, 66, spo2=97)
    for i in range(24):
        add(db, TODAY, i, 66, spo2=90)
    assert spo2_obs(c) is None

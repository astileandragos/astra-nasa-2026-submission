import sqlite3

import pytest

from app import create_app

GOOD = {
    "device_id": "ASTRA-01",
    "heart_rate_bpm": 72,
    "spo2_percent": 98,
    "accel_x_g": 0.01,
    "accel_y_g": 0.02,
    "accel_z_g": 0.99,
    "gyro_x_dps": 0.2,
    "gyro_y_dps": 0.1,
    "gyro_z_dps": 0.3,
    "signal_quality": "good",
    "source": "simulated",
    "uptime_ms": 1000,
}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "test.db")
    return app.test_client(), tmp_path / "test.db"


def test_health(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_post_saves_row_with_server_time(client):
    c, db = client
    r = c.post("/api/measurements", json=GOOD)
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "ok" and body["received_at"]
    row = sqlite3.connect(db).execute("select heart_rate_bpm, received_at, source from measurements").fetchone()
    assert row == (72, body["received_at"], "simulated")
    assert "+" in row[1] or "-" in row[1][10:]  # has a time zone offset


def test_nulls_and_missing_fields_are_stored_as_null(client):
    c, db = client
    payload = {**GOOD, "heart_rate_bpm": None}
    del payload["spo2_percent"]
    assert c.post("/api/measurements", json=payload).status_code == 201
    row = sqlite3.connect(db).execute("select heart_rate_bpm, spo2_percent from measurements").fetchone()
    assert row == (None, None)


@pytest.mark.parametrize("field", ["heart_rate_bpm", "spo2_percent"])
def test_zero_is_rejected(client, field):
    c, db = client
    r = c.post("/api/measurements", json={**GOOD, field: 0})
    assert r.status_code == 400
    assert r.get_json()["message"] == "Use null for missing values, not 0"
    assert sqlite3.connect(db).execute("select count(*) from measurements").fetchone()[0] == 0


@pytest.mark.parametrize("field,value", [
    ("heart_rate_bpm", 301), ("heart_rate_bpm", -5), ("spo2_percent", 101),
    ("accel_x_g", 17), ("gyro_z_dps", -2001), ("heart_rate_bpm", "72"), ("spo2_percent", True),
])
def test_out_of_range_or_wrong_type_rejected(client, field, value):
    c, _ = client
    r = c.post("/api/measurements", json={**GOOD, field: value})
    assert r.status_code == 400 and r.get_json()["field"] == field


@pytest.mark.parametrize("change", [
    {"source": "made_up"}, {"source": None}, {"device_id": ""}, {"signal_quality": "great"}, {"uptime_ms": -1},
])
def test_bad_labels_rejected(client, change):
    c, _ = client
    assert c.post("/api/measurements", json={**GOOD, **change}).status_code == 400


def test_non_json_body_rejected_and_server_keeps_working(client):
    c, _ = client
    assert c.post("/api/measurements", data="hello").status_code == 400
    assert c.post("/api/measurements", json=[1, 2]).status_code == 400
    assert c.post("/api/measurements", json=GOOD).status_code == 201


# ---- read endpoints ----
def post(c, **change):
    r = c.post("/api/measurements", json={**GOOD, **change})
    assert r.status_code == 201
    return r.get_json()


def test_latest_404_when_empty(client):
    c, _ = client
    r = c.get("/api/measurements/latest")
    assert r.status_code == 404
    assert r.get_json() == {"status": "error", "message": "no measurements yet"}


def test_latest_returns_most_recent_with_all_fields(client):
    c, _ = client
    post(c, heart_rate_bpm=70)
    post(c, heart_rate_bpm=None)
    r = c.get("/api/measurements/latest")
    body = r.get_json()
    assert r.status_code == 200 and isinstance(body, dict)
    assert body["heart_rate_bpm"] is None  # null stays null, not 0
    assert set(body) == {"id", "received_at", "device_id", "heart_rate_bpm", "spo2_percent",
                         "accel_x_g", "accel_y_g", "accel_z_g", "gyro_x_dps", "gyro_y_dps",
                         "gyro_z_dps", "signal_quality", "source", "uptime_ms"}


def test_list_empty_is_empty_array(client):
    c, _ = client
    r = c.get("/api/measurements")
    assert r.status_code == 200 and r.get_json() == []


def test_list_newest_first_and_default_limit(client):
    c, _ = client
    for i in range(55):
        post(c, uptime_ms=i)
    items = c.get("/api/measurements").get_json()
    assert len(items) == 50
    assert items[0]["uptime_ms"] == 54 and items[-1]["uptime_ms"] == 5


def test_list_limit_and_max(client):
    c, _ = client
    for i in range(105):
        post(c, uptime_ms=i)
    assert len(c.get("/api/measurements?limit=3").get_json()) == 3
    assert len(c.get("/api/measurements?limit=500").get_json()) == 100  # capped at 100


@pytest.mark.parametrize("q", ["limit=0", "limit=-2", "limit=abc"])
def test_list_bad_limit_rejected(client, q):
    c, _ = client
    r = c.get(f"/api/measurements?{q}")
    assert r.status_code == 400 and r.get_json()["field"] == "limit"


def test_list_filter_by_source(client):
    c, _ = client
    post(c, source="simulated")
    post(c, source="live_hardware")
    post(c, source="simulated")
    items = c.get("/api/measurements?source=live_hardware").get_json()
    assert len(items) == 1 and items[0]["source"] == "live_hardware"
    assert c.get("/api/measurements?source=nope").status_code == 400


def test_list_since_filter(client):
    c, db = client
    old = sqlite3.connect(db)
    old.execute("INSERT INTO measurements (received_at, device_id, source) VALUES "
                "('2026-11-14T08:00:00+02:00','OLD','simulated'),"
                "('2026-11-14T09:00:00+02:00','MID','simulated')")
    old.commit()
    post(c)  # received now, later than both
    ids = [i["device_id"] for i in c.get("/api/measurements?since=2026-11-14T08:30:00%2B02:00").get_json()]
    assert ids == ["ASTRA-01", "MID"]  # newest first, OLD excluded
    # a raw "+" (turned into a space by the URL) still works
    assert len(c.get("/api/measurements?since=2026-11-14T08:30:00+02:00").get_json()) == 2
    # the same instant written in UTC gives the same answer
    assert len(c.get("/api/measurements?since=2026-11-14T06:30:00Z").get_json()) == 2
    assert c.get("/api/measurements?since=yesterday").status_code == 400


# ---- dashboard serving and CORS ----
def test_dashboard_served_from_frontend_folder(tmp_path):
    (tmp_path / "index.html").write_text("<h1>ASTRA</h1>")
    (tmp_path / "app.js").write_text("// js")
    c = create_app(tmp_path / "t.db", frontend_dir=tmp_path).test_client()
    assert b"ASTRA" in c.get("/").data
    assert c.get("/app.js").status_code == 200
    assert c.get("/missing.css").status_code == 404
    assert c.get("/api/nope").get_json()["message"] == "not found"


def test_dashboard_404_message_when_no_index(tmp_path):
    c = create_app(tmp_path / "t.db", frontend_dir=tmp_path).test_client()
    assert c.get("/").status_code == 404


def test_cors_header_on_api(client):
    c, _ = client
    r = c.get("/api/health", headers={"Origin": "http://localhost:5500"})
    assert r.headers.get("Access-Control-Allow-Origin") in ("*", "http://localhost:5500")


# ---- daily check-in (journal) ----
J = {"date": "2026-11-14", "sleep_hours": 6.5, "mood": 3, "energy": 4, "stress": 2, "fatigue": 3, "note": "ok"}


def test_journal_save_and_read_back(client):
    c, _ = client
    r = c.post("/api/journal", json=J)
    assert r.status_code == 201 and r.get_json()["date"] == "2026-11-14"
    got = c.get("/api/journal?date=2026-11-14")
    body = got.get_json()
    assert got.status_code == 200 and body["source"] == "self_reported" and body["received_at"]
    assert {k: body[k] for k in J} == J


def test_journal_same_date_replaces_and_skipped_is_null(client):
    c, _ = client
    c.post("/api/journal", json=J)
    c.post("/api/journal", json={"date": "2026-11-14", "mood": 5})
    body = c.get("/api/journal?date=2026-11-14").get_json()
    assert body["mood"] == 5 and body["sleep_hours"] is None and body["stress"] is None
    assert c.get("/api/journal").get_json()["count"] == 1


def test_journal_list_newest_date_first_and_404(client):
    c, _ = client
    for d in ("2026-11-12", "2026-11-14", "2026-11-13"):
        c.post("/api/journal", json={**J, "date": d})
    items = c.get("/api/journal").get_json()["items"]
    assert [i["date"] for i in items] == ["2026-11-14", "2026-11-13", "2026-11-12"]
    assert len(c.get("/api/journal?limit=2").get_json()["items"]) == 2
    assert c.get("/api/journal?date=2020-01-01").status_code == 404
    assert c.get("/api/journal?date=bad").status_code == 400


def test_journal_does_not_touch_measurements(client):
    c, _ = client
    c.post("/api/journal", json=J)
    assert c.get("/api/measurements/latest").status_code == 404


@pytest.mark.parametrize("change", [
    {"date": None}, {"date": "14-11-2026"}, {"date": "2026-02-31"},
    {"mood": 0}, {"mood": 6}, {"stress": 2.5}, {"energy": "3"}, {"fatigue": True},
    {"sleep_hours": 25}, {"sleep_hours": -1}, {"sleep_hours": "7"}, {"note": 5}, {"note": "x" * 501},
])
def test_journal_bad_values_rejected(client, change):
    c, _ = client
    r = c.post("/api/journal", json={**J, **change})
    assert r.status_code == 400 and r.get_json()["status"] == "error"


def test_journal_needs_at_least_one_answer(client):
    c, _ = client
    r = c.post("/api/journal", json={"date": "2026-11-14", "note": "only text"})
    assert r.status_code == 400
    assert c.post("/api/journal", data="nope").status_code == 400
    assert c.post("/api/journal", json=[1]).status_code == 400

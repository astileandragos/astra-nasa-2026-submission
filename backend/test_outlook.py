"""The radiation outlook: clear, watch, prepare, build the shelter, shelter."""
from datetime import datetime, timedelta, timezone

import pytest

import outlook
import radiation
from app import create_app, get_db


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "o.db"
    app = create_app(db)
    return app.test_client(), db


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def quiet_rows(n, last=0.2, rising_to=None):
    t = now()
    rows = []
    for i in range(n):
        when = t - timedelta(minutes=5 * (n - 1 - i))
        flux = last
        if rising_to and i >= n - 4:
            flux = last * (rising_to / last) ** ((i - (n - 4)) / 3)
        rows.append((radiation._iso(when), flux))
    return rows


def stage(db, rows, extras=None, source="external"):
    with get_db(db) as conn:
        radiation._insert_samples(conn, source, rows)
        conn.commit()
        return outlook.outlook(conn, source, extras, now())["stage"]["key"]


def extras(flare=None, radio=None, prob=None, warning=None):
    return {"available": True, "errors": [], "flare": flare, "radio": radio, "proton_warning": warning, "prob_s1": prob}


def flare(cls_flux, minutes_ago=30):
    return {"flux": cls_flux, "class": outlook.flare_class(cls_flux), "at": radiation._iso(now() - timedelta(minutes=minutes_ago))}


def test_quiet_sun_is_clear(env):
    _, db = env
    assert stage(db, quiet_rows(24), extras(prob=5)) == "clear"


def test_a_strong_flare_or_radio_burst_or_high_forecast_is_a_watch(env):
    _, db = env
    assert stage(db, quiet_rows(24), extras(flare=flare(5e-5))) == "watch"


def test_radio_burst_and_forecast_alone_are_a_watch(tmp_path):
    for ex in (extras(radio={"type": "II", "at": radiation._iso(now())}), extras(prob=30)):
        db = tmp_path / f"{id(ex)}.db"
        create_app(db)
        assert stage(db, quiet_rows(24), ex) == "watch"


def test_a_weak_flare_and_a_low_forecast_are_clear(env):
    _, db = env
    assert stage(db, quiet_rows(24), extras(flare=flare(2e-6), prob=10)) == "clear"


def test_a_rising_particle_level_is_prepare(env):
    _, db = env
    assert stage(db, quiet_rows(30, last=0.3, rising_to=4.0), extras(prob=5)) == "prepare"


def test_a_very_strong_flare_is_prepare_but_an_old_one_is_not(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    create_app(a), create_app(b)
    assert stage(a, quiet_rows(24), extras(flare=flare(1.5e-4, 30))) == "prepare"
    assert stage(b, quiet_rows(24), extras(flare=flare(1.5e-4, 5 * 60))) == "watch"     # 5 hours ago: only a watch


def test_s2_and_s3_mean_build_and_s4_means_shelter(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    create_app(a), create_app(b)
    for db, level, want in ((a, 3, "build"), (b, 4, "shelter")):
        with get_db(db) as conn:
            radiation.simulate(conn, f"s{level}")
            assert outlook.outlook(conn, "simulated", None, now())["stage"]["key"] == want


def test_no_data_is_unknown_and_never_clear(env):
    _, db = env
    with get_db(db) as conn:
        assert outlook.outlook(conn, "external", None, now())["stage"]["key"] == "unknown"


def test_every_step_is_labelled_nasa_or_astra_and_the_limits_are_stated(env):
    _, db = env
    with get_db(db) as conn:
        radiation.simulate(conn, "prepare")
        out = outlook.outlook(conn, "simulated", None, now())
    assert out["stage"]["key"] == "prepare" and out["stage"]["steps"]
    assert {s["tag"] for s in out["stage"]["steps"]} <= {"nasa", "astra"}
    assert "cannot predict" in out["limits"] and len(out["sources"]) >= 2


def test_parsers_read_noaa_shapes_and_ignore_junk():
    t = now()
    xr = [{"time_tag": radiation._iso(t - timedelta(hours=1)), "flux": 5.2e-5, "energy": "0.1-0.8nm"},
          {"time_tag": radiation._iso(t - timedelta(hours=1)), "flux": 9e-3, "energy": "0.05-0.4nm"},
          {"time_tag": radiation._iso(t - timedelta(hours=9)), "flux": 3e-4, "energy": "0.1-0.8nm"}, "junk", {"flux": "x"}]
    f = outlook.parse_flare(xr, t)
    assert f["class"] == "M5.2" and outlook.parse_flare("junk", t) is None
    alerts = [{"issue_datetime": (t - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S.000"), "message": "ALERT: Type II Radio Emission"},
              {"issue_datetime": "bad", "message": "ALERT: Type IV Radio Emission"}]
    radio, warning = outlook.parse_alerts(alerts, t)
    assert radio["type"] == "II" and warning is None
    assert outlook.parse_probability({"1": {"S": {"Prob": "30"}}}) == 30 and outlook.parse_probability({}) is None


def test_fetch_extras_survives_failures():
    def broken(url):
        raise OSError("offline")
    out = outlook.fetch_extras(broken, now())
    assert out["available"] is False and len(out["errors"]) == 3
    only_scales = outlook.fetch_extras(lambda u: {"1": {"S": {"Prob": "40"}}} if "scales" in u else (_ for _ in ()).throw(OSError("x")), now())
    assert only_scales["available"] and only_scales["prob_s1"] == 40


def test_endpoint_and_the_demo_scenarios(env):
    c, _ = env
    assert c.post("/api/radiation/simulate", json={"scenario": "watch"}).status_code in (200, 201)
    body = c.get("/api/radiation/outlook?source=simulated").get_json()
    assert body["stage"]["key"] == "watch" and any(s["key"] == "flare" and s["active"] for s in body["signals"])
    c.post("/api/radiation/simulate", json={"scenario": "prepare"})
    assert c.get("/api/radiation/outlook?source=simulated").get_json()["stage"]["key"] == "prepare"
    c.post("/api/radiation/simulate", json={"scenario": "quiet"})
    assert c.get("/api/radiation/outlook?source=simulated").get_json()["stage"]["key"] == "clear"

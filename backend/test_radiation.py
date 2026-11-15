"""Tests for the Radiation Risk Monitor (docs/api_contract.md section 6.15, docs/RADIATION_MONITOR.md)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import radiation
from app import create_app, get_db

T0 = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)


def series(fluxes, start=T0, step=5):
    """Samples (utc_iso, flux) at a 5 minute cadence."""
    return [(radiation._iso(start + timedelta(minutes=step * i)), f) for i, f in enumerate(fluxes)]


def kinds(result):
    return [(a["kind"], a["level"]) for a in result["alerts"]]


@pytest.fixture
def env(tmp_path):
    db = tmp_path / "r.db"
    calls = {"n": 0, "data": []}

    def fake_fetch(_url):
        calls["n"] += 1
        if isinstance(calls["data"], Exception):
            raise calls["data"]
        return calls["data"]

    app = create_app(db, noaa_fetch=fake_fetch)
    return app.test_client(), db, calls


def noaa(fluxes, start=T0, channel=">=10 MeV"):
    return [{"time_tag": radiation._iso(start + timedelta(minutes=5 * i)).replace("+00:00", "Z"), "satellite": 18,
             "flux": f, "energy": channel} for i, f in enumerate(fluxes)]


# ---------- classification ----------
@pytest.mark.parametrize("flux,expected", [(0.0, 0), (9.99, 0), (10, 1), (99.99, 1), (100, 2), (999, 2), (1000, 3),
                                           (9999, 3), (10000, 4), (99999, 4), (100000, 5), (1e7, 5)])
def test_s_class_uses_the_noaa_thresholds(flux, expected):
    assert radiation.s_class(flux) == expected


def test_alert_level_mapping():
    assert [radiation.alert_level(s) for s in range(6)] == [0, 1, 2, 2, 3, 3]


# ---------- NOAA parsing ----------
def test_parse_keeps_only_the_10_mev_channel_and_normalises_time():
    records = noaa([1.5, 2.5]) + noaa([99, 99], channel=">=100 MeV")
    samples, skipped = radiation.parse_noaa(records)
    assert [(t, f) for t, f, _ in samples] == [("2026-11-14T08:00:00+00:00", 1.5), ("2026-11-14T08:05:00+00:00", 2.5)]
    assert skipped == 0 and samples[0][2] == 18


def test_parse_skips_missing_and_invalid_values_never_zero():
    records = noaa([None, -1, float("nan"), True, "7", 5.0])
    samples, skipped = radiation.parse_noaa(records)
    assert [f for _, f, _ in samples] == [5.0] and skipped == 5
    bad_time = [{"time_tag": "not a time", "flux": 3, "energy": ">=10 MeV"}, {"flux": 3, "energy": ">=10 MeV"}]
    assert radiation.parse_noaa(bad_time) == ([], 2)
    with pytest.raises(ValueError):
        radiation.parse_noaa({"not": "a list"})


# ---------- the state machine ----------
def test_quiet_flux_gives_no_event():
    result = radiation.evaluate(series([0.2] * 40), "simulated")
    assert result["events"] == [] and result["alerts"] == [] and result["state"]["level"] == 0


def test_a_short_spike_is_not_an_event():
    result = radiation.evaluate(series([0.2, 0.2, 500, 0.2, 0.2, 300, 300, 0.2, 0.2]), "simulated")
    assert result["alerts"] == [] and result["state"]["level"] == 0       # needs 3 samples in a row


def test_onset_after_three_consecutive_samples_starts_at_the_first_of_them():
    samples = series([0.2, 0.2, 15, 20, 30, 30])
    result = radiation.evaluate(samples, "external")
    assert kinds(result) == [("onset", 1)]
    assert result["events"][0]["started_at"] == samples[2][0]
    assert result["alerts"][0]["at"] == samples[4][0]                      # confirmed on the third sample
    assert result["state"]["level"] == 1 and result["state"]["event_id"] == result["events"][0]["id"]


def test_onset_level_is_the_lowest_of_the_run():
    assert kinds(radiation.evaluate(series([0.2, 50, 500, 500]), "x")) == [("onset", 1)]
    assert kinds(radiation.evaluate(series([0.2, 500, 600, 700]), "x")) == [("onset", 2)]


def test_escalation_needs_two_samples_and_one_spike_is_ignored():
    base = [20, 20, 20]
    assert kinds(radiation.evaluate(series(base + [600, 20, 20]), "x")) == [("onset", 1)]
    result = radiation.evaluate(series(base + [600, 700, 700]), "x")
    assert kinds(result) == [("onset", 1), ("escalation", 2)]
    result = radiation.evaluate(series(base + [600, 700, 20000, 30000]), "x")
    assert kinds(result) == [("onset", 1), ("escalation", 2), ("escalation", 3)]
    assert result["events"][0]["level_max"] == 3 and result["events"][0]["s_class_peak"] == 4


def test_a_steady_event_makes_exactly_one_alert():
    result = radiation.evaluate(series([300] * 200), "x")                  # 16 hours at the same level
    assert len(result["alerts"]) == 1 and len(result["events"]) == 1


def test_easing_and_recovery_use_hysteresis_and_six_samples():
    # 8 pfu is below S1 but not below half of it, so it does not count as "lower": no recovery.
    assert kinds(radiation.evaluate(series([20, 20, 20] + [8] * 12), "x")) == [("onset", 1)]
    # 2 pfu for six samples in a row ends the event.
    result = radiation.evaluate(series([20, 20, 20] + [2] * 5), "x")
    assert kinds(result) == [("onset", 1)] and result["state"]["level"] == 1   # only five so far
    result = radiation.evaluate(series([20, 20, 20] + [2] * 6), "x")
    assert kinds(result) == [("onset", 1), ("recovery", 0)] and result["state"]["level"] == 0
    event = result["events"][0]
    assert event["active"] is False and event["ended_at"] == radiation._iso(T0 + timedelta(minutes=15))   # first quiet sample
    assert result["alerts"][-1]["requires_ack"] is False
    # from level 2 down to level 1 is "easing"; the alert does not ask for an acknowledgement
    result = radiation.evaluate(series([600] * 4 + [30] * 6), "x")
    assert kinds(result) == [("onset", 2), ("easing", 1)] and result["alerts"][-1]["requires_ack"] is False


def test_a_new_event_after_recovery_is_a_second_event_with_its_own_alerts():
    result = radiation.evaluate(series([20] * 3 + [2] * 6 + [0.2] * 3 + [40] * 4), "x")
    assert [e["active"] for e in result["events"]] == [False, True]
    assert len({a["id"] for a in result["alerts"]}) == len(result["alerts"]) == 3


def test_a_long_gap_restarts_the_counters():
    first = series([20, 20])
    later = series([20], start=T0 + timedelta(hours=2))
    assert radiation.evaluate(first + later, "x")["alerts"] == []          # 2 + gap + 1 is not 3 in a row
    assert kinds(radiation.evaluate(series([20, 20, 20]), "x")) == [("onset", 1)]


def test_replaying_gives_the_same_ids():
    samples = series([20] * 3 + [600] * 3)
    ids = [a["id"] for a in radiation.evaluate(samples, "external")["alerts"]]
    assert ids == [a["id"] for a in radiation.evaluate(samples, "external")["alerts"]]
    assert ids[0].startswith("external:20261114T08") and ids[0].endswith(":1")


def test_peak_flux_is_tracked():
    result = radiation.evaluate(series([20, 20, 20, 900, 5000, 700, 30]), "x")
    event = result["events"][0]
    assert event["peak_flux_pfu"] == 5000 and event["s_class_peak"] == 3 and event["duration_min"] == 30


# ---------- data status ----------
def test_data_status_levels():
    now = T0 + timedelta(hours=1)
    assert radiation.data_status([], now)["status"] == "no_data"
    assert radiation.data_status(series([1], start=now - timedelta(minutes=10)), now)["status"] == "ok"
    assert radiation.data_status(series([1], start=now - timedelta(minutes=40)), now)["status"] == "delayed"
    assert radiation.data_status(series([1], start=now - timedelta(hours=5)), now)["status"] == "stale"


# ---------- NOAA refresh through the API ----------
def test_refresh_stores_samples_once_and_reports_status(env):
    c, db, calls = env
    calls["data"] = noaa([0.2] * 12, start=datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=60))
    first = c.post("/api/radiation/refresh").get_json()
    assert first["inserted"] == 12 and first["error"] is None and first["file"] == "integral-protons-1-day.json"
    again = c.post("/api/radiation/refresh").get_json()
    assert again["inserted"] == 0 and again["file"] == "integral-protons-6-hour.json"      # later calls use the small file
    status = c.get("/api/radiation/status?source=external").get_json()
    assert status["data_status"] == "ok" and status["state"]["level"] == 0 and status["last_fetch_at"]
    assert status["label"] == "external" and "not the radiation dose" in status["what_it_is"]


def test_refresh_failure_keeps_old_data_and_is_reported(env):
    c, db, calls = env
    calls["data"] = noaa([0.2] * 5, start=datetime.now(timezone.utc) - timedelta(minutes=30))
    assert c.post("/api/radiation/refresh").status_code == 200
    calls["data"] = TimeoutError("timed out")
    failed = c.post("/api/radiation/refresh")
    assert failed.status_code == 502 and "TimeoutError" in failed.get_json()["error"]
    status = c.get("/api/radiation/status?source=external").get_json()
    assert status["fetch_error"] and status["state"]["flux_pfu"] is not None          # the old samples are still there
    calls["data"] = noaa([0.3] * 3, start=datetime.now(timezone.utc) - timedelta(minutes=10))
    assert c.post("/api/radiation/refresh").status_code == 200
    assert c.get("/api/radiation/status?source=external").get_json()["fetch_error"] is None


def test_no_data_is_reported_not_zero(env):
    c, _, _ = env
    status = c.get("/api/radiation/status?source=external").get_json()
    assert status["data_status"] == "no_data" and status["state"]["flux_pfu"] is None and status["state"]["s_class_now"] is None
    assert status["oled"]["footer"] == "NO DATA"
    assert c.get("/api/radiation/flux?source=external").get_json()["samples"] == []


def test_a_real_event_in_the_fetched_data_raises_the_level(env):
    c, _, calls = env
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=55)
    calls["data"] = noaa([0.2] * 4 + [120, 150, 180, 200, 220, 240], start=start)
    c.post("/api/radiation/refresh")
    status = c.get("/api/radiation/status?source=external").get_json()
    assert status["state"]["level"] == 2 and status["state"]["s_class_now"] == 2
    assert status["alert"]["name"] == "HIGH" and status["ack_pending"]["alert_id"].startswith("external:")


# ---------- alerts, acknowledgement and the OLED ----------
def storm(c, scenario="s2"):
    assert c.post("/api/radiation/simulate", json={"scenario": scenario}).status_code == 201


def test_oled_lines_fit_the_display_for_every_level(env):
    c, _, _ = env
    for scenario, level in [("quiet", 0), ("s1", 1), ("s2", 2), ("s4", 3)]:
        storm(c, scenario)
        answer = c.get("/api/radiation/alert?source=simulated").get_json()
        assert answer["level"] == level and len(answer["lines"]) == 4
        assert all(len(line) <= 21 for line in answer["lines"]) and len(answer["footer"]) <= 21
        assert answer["lines"][1].startswith("S")
    assert answer["beep"] == "continuous" and answer["repeat_until_ack"] is True
    assert "SHELTER" in " ".join(answer["lines"])


def test_acknowledgement_silences_the_alert_but_keeps_the_level(env):
    c, _, _ = env
    storm(c, "s3")
    before = c.get("/api/radiation/alert?source=simulated").get_json()
    assert before["ack_pending"] and before["alert_id"] and before["beep"] != "none"
    done = c.post("/api/radiation/ack", json={"alert_id": before["alert_id"]})
    assert done.status_code == 200 and done.get_json()["alert"]["acknowledged_at"]
    after = c.get("/api/radiation/alert?source=simulated").get_json()
    assert after["level"] == before["level"] and after["ack_pending"] is False
    assert after["beep"] == "none" and after["footer"] == "" and after["alert_id"] is None


def test_a_new_escalation_asks_for_a_new_acknowledgement(env):
    c, _, _ = env
    storm(c, "s1")
    first = c.get("/api/radiation/alert?source=simulated").get_json()
    c.post("/api/radiation/ack", json={"alert_id": first["alert_id"]})
    for flux in (300, 320):
        c.post("/api/radiation/simulate", json={"flux_pfu": flux})
    again = c.get("/api/radiation/alert?source=simulated").get_json()
    assert again["level"] == 2 and again["ack_pending"] and again["alert_id"] != first["alert_id"]


def test_ack_input_checks(env):
    c, _, _ = env
    assert c.post("/api/radiation/ack", json={"alert_id": "nope"}).status_code == 404
    assert c.post("/api/radiation/ack", json={}).status_code == 400
    assert c.post("/api/radiation/ack", data="x", content_type="text/plain").status_code == 400


def test_events_and_alerts_lists_are_newest_first(env):
    c, _, _ = env
    storm(c, "s4")
    body = c.get("/api/radiation/events?source=simulated").get_json()
    assert len(body["events"]) == 1 and body["events"][0]["active"] and body["events"][0]["s_class_peak"] == 4
    assert [a["level"] for a in body["alerts"]] == [3, 2, 1] and body["alerts"][0]["kind"] == "escalation"
    assert body["alerts"][-1]["kind"] == "onset" and all("actions" in a for a in body["alerts"])


# ---------- simulation ----------
def test_scenarios_reach_their_class(env):
    c, _, _ = env
    expected = {"quiet": 0, "s1": 1, "s2": 2, "s3": 2, "s4": 3}
    for scenario, level in expected.items():
        storm(c, scenario)
        assert c.get("/api/radiation/status?source=simulated").get_json()["state"]["level"] == level


def test_simulate_replaces_old_simulated_data_and_is_repeatable(env):
    c, db, _ = env
    storm(c, "s3")
    storm(c, "s3")
    with get_db(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM radiation_samples WHERE source='simulated'").fetchone()[0] == 72
        assert conn.execute("SELECT COUNT(*) FROM radiation_dose WHERE source='simulated'").fetchone()[0] == 1
    storm(c, "quiet")
    assert c.get("/api/radiation/events?source=simulated").get_json()["events"] == []


def test_simulation_never_touches_real_data(env):
    c, db, calls = env
    calls["data"] = noaa([0.2] * 6, start=datetime.now(timezone.utc) - timedelta(minutes=40))
    c.post("/api/radiation/refresh")
    storm(c, "s4")
    with get_db(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM radiation_samples WHERE source='external'").fetchone()[0] == 6
    assert c.get("/api/radiation/status?source=external").get_json()["state"]["level"] == 0


def test_manual_samples_can_trigger_an_event(env):
    c, _, _ = env
    storm(c, "quiet")
    for flux in (50, 60, 70):
        assert c.post("/api/radiation/simulate", json={"flux_pfu": flux}).status_code == 201
    assert c.get("/api/radiation/status?source=simulated").get_json()["state"]["level"] == 1


def test_simulate_input_checks(env):
    c, _, _ = env
    for body in ({"scenario": "s9"}, {"flux_pfu": -1}, {"flux_pfu": "x"}, {"flux_pfu": True}, {}, {"flux_pfu": float("inf")}):
        assert c.post("/api/radiation/simulate", json=body).status_code == 400, body
    assert c.post("/api/radiation/simulate", data="nope", content_type="text/plain").status_code == 400


# ---------- history ----------
def test_flux_history_and_input_checks(env):
    c, _, _ = env
    storm(c, "s2")
    body = c.get("/api/radiation/flux?source=simulated&hours=3").get_json()
    assert body["channel"] == ">=10 MeV" and body["unit"] == "pfu" and 30 <= len(body["samples"]) <= 40
    assert [t["flux_pfu"] for t in body["thresholds"]] == [10, 100, 1000, 10000, 100000]
    assert {"time", "flux_pfu", "s_class"} <= set(body["samples"][0])
    assert c.get("/api/radiation/flux?hours=0").status_code == 400
    assert c.get("/api/radiation/flux?hours=500").status_code == 400
    assert c.get("/api/radiation/status?source=oops").status_code == 400
    assert c.get("/api/radiation/status").get_json()["source"] == "external"          # default is the real data


# ---------- the educational budget ----------
def make_conn(tmp_path):
    db = tmp_path / "b.db"
    create_app(db)
    return get_db(db)


def test_budget_follows_the_formula(tmp_path):
    with make_conn(tmp_path) as conn:
        radiation.set_config(conn, "simulated", {"budget_msv": 100, "initial_msv": 20, "baseline_rate_msv_day": 0.5}, T0)
        b = radiation.budget(conn, "simulated", T0)
        assert (b["accumulated_msv"], b["remaining_msv"], b["estimated_days_remaining"]) == (20, 80, 160)
        later = radiation.budget(conn, "simulated", T0 + timedelta(days=10))      # 10 days of background at 0.5 mSv/day
        assert later["baseline_accrued_msv"] == 5 and later["accumulated_msv"] == 25 and later["remaining_msv"] == 75
        assert later["estimated_days_remaining"] == 150
        assert "D_remaining = D_budget - D_accumulated" in later["formula"] and later["kind"] == "estimate"
        assert any("not a medically certified" in a for a in later["assumptions"])


def test_an_event_dose_updates_remaining_budget_days_and_explains_why(tmp_path):
    with make_conn(tmp_path) as conn:
        radiation.set_config(conn, "simulated", {"budget_msv": 100, "initial_msv": 20, "baseline_rate_msv_day": 0.5}, T0)
        conn.execute("INSERT INTO radiation_dose (source, at, msv, origin, event_ref, note) VALUES "
                     "('simulated', ?, 10, 'simulated_event', 'e1', 'Simulated S3 event')", (radiation._iso(T0),))
        b = radiation.budget(conn, "simulated", T0)
        assert b["accumulated_msv"] == 30 and b["remaining_msv"] == 70 and b["estimated_days_remaining"] == 140
        entry = b["entries"][0]
        assert (entry["remaining_before_msv"], entry["remaining_after_msv"]) == (80, 70)
        assert (entry["days_before"], entry["days_after"]) == (160, 140) and entry["label"] == "simulated"
        assert "80 -> 70" in b["why_it_changed"] and "160 -> 140" in b["why_it_changed"]


def test_budget_edge_cases(tmp_path):
    with make_conn(tmp_path) as conn:
        radiation.set_config(conn, "external", {"budget_msv": 10, "initial_msv": 9, "baseline_rate_msv_day": 0}, T0)
        b = radiation.budget(conn, "external", T0)
        assert b["estimated_days_remaining"] is None                             # no background rate: no estimate, not infinity
        radiation.add_operator_dose(conn, "external", 5, "Dosimeter reading", T0)
        b = radiation.budget(conn, "external", T0)
        assert b["exceeded"] is True and b["remaining_msv"] == 0 and b["used_share"] == 1.0
        radiation.set_config(conn, "external", {"baseline_rate_msv_day": 1}, T0)
        assert radiation.budget(conn, "external", T0)["estimated_days_remaining"] == 0


def test_budgets_of_the_two_sources_are_separate(env):
    c, _, calls = env
    storm(c, "s3")
    assert c.get("/api/radiation/budget?source=simulated").get_json()["event_dose_msv"] == 5
    real = c.get("/api/radiation/budget?source=external").get_json()
    assert real["event_dose_msv"] == 0 and real["entries"] == [] and "not estimated from NOAA flux" in real["dose_status"]
    assert real["label"] == "self_reported" and c.get("/api/radiation/budget?source=simulated").get_json()["label"] == "simulated"


def test_real_events_never_add_dose_by_themselves(env):
    c, _, calls = env
    calls["data"] = noaa([0.2] * 3 + [5000] * 10, start=datetime.now(timezone.utc) - timedelta(minutes=70))
    c.post("/api/radiation/refresh")
    assert c.get("/api/radiation/status?source=external").get_json()["state"]["level"] == 2
    assert c.get("/api/radiation/budget?source=external").get_json()["event_dose_msv"] == 0


def test_operator_dose_through_the_api(env):
    c, _, _ = env
    answer = c.post("/api/radiation/dose?source=external", json={"msv": 2.5, "note": "Badge reading"})
    body = answer.get_json()
    assert answer.status_code == 201 and body["event_dose_msv"] == 2.5 and body["entries"][0]["origin"] == "operator_entered"
    assert body["entries"][0]["note"] == "Badge reading" and body["accumulated_msv"] >= 2.5
    for bad in ({"msv": 0}, {"msv": -3}, {"msv": "x"}, {"msv": True}, {}, {"msv": 5000}, {"msv": 1, "note": "x" * 300}):
        assert c.post("/api/radiation/dose?source=external", json=bad).status_code == 400, bad


def test_budget_settings_through_the_api(env):
    c, _, _ = env
    body = c.post("/api/radiation/budget?source=simulated", json={"budget_msv": 50, "initial_msv": 10}).get_json()
    assert body["budget_msv"] == 50 and body["initial_msv"] == 10 and body["baseline_rate_msv_day"] == 0.5
    assert c.get("/api/radiation/budget?source=external").get_json()["budget_msv"] == 600        # the other source keeps NASA's 600 mSv career limit
    for bad in ({"budget_msv": 0}, {"budget_msv": "x"}, {"budget_msv": True}, {"initial_msv": -1},
                {"baseline_rate_msv_day": 99}, {"colour": 1}):
        assert c.post("/api/radiation/budget?source=simulated", json=bad).status_code == 400, bad


# ---------- the Overview notification ----------
def notices(c, source="simulated"):
    return {n["id"]: n for n in c.get(f"/api/notifications?source={source}").get_json()["notifications"]}


def test_overview_gets_a_radiation_notification_when_an_event_is_active(env):
    c, _, _ = env
    storm(c, "s1")
    item = notices(c)["radiation"]
    assert item["level"] == "warning" and item["page"] == "radiation.html" and item["target"] == "rad-status-h"
    storm(c, "s4")
    item = notices(c)["radiation"]
    assert item["level"] == "danger" and "SEVERE" in item["title"]
    assert any("shelter" in step.lower() for step in item["advice"]["steps"]) and "not NASA flight rules" in item["advice"]["meaning"]


def test_no_radiation_notification_without_data_or_for_a_quiet_simulation(env):
    c, _, _ = env
    assert "radiation" not in notices(c)
    storm(c, "quiet")
    assert "radiation" not in notices(c)


def test_quiet_fresh_noaa_data_gives_a_green_notification_and_stale_data_none(env):
    c, db, calls = env
    calls["data"] = noaa([0.2] * 6, start=datetime.now(timezone.utc) - timedelta(minutes=30))
    c.post("/api/radiation/refresh")
    assert notices(c)["radiation"]["level"] == "ok"
    with get_db(db) as conn:
        conn.execute("UPDATE radiation_samples SET time_tag = replace(time_tag, '2026', '2020')")
    assert "radiation" not in notices(c)


def test_the_radiation_page_has_the_target_heading():
    page = Path(__file__).resolve().parent.parent / "frontend" / "radiation.html"
    assert 'id="rad-status-h"' in page.read_text(encoding="utf-8")


# ---------- data unavailable and recovery notifications ----------
def test_no_data_is_a_warning_not_normal(env):
    c, db, _ = env
    with get_db(db) as conn:
        item = radiation.notice_item(conn, T0)
    assert item["id"] == "radiation_data" and item["level"] == "warning" and "unavailable" in item["title"]
    assert "Do not assume" in item["advice"]["meaning"]


def test_stale_data_is_a_warning_with_the_last_time(env):
    c, db, _ = env
    with get_db(db) as conn:
        radiation._insert_samples(conn, "external", series([0.2] * 6))
        item = radiation.notice_item(conn, T0 + timedelta(hours=3))
    assert item["id"] == "radiation_data" and "08:" in item["message"]


def test_recovery_notice_appears_after_an_event_ends_and_goes_away(env):
    c, db, _ = env
    flux = [0.2] * 6 + [20] * 4 + [0.2] * 12
    with get_db(db) as conn:
        radiation._insert_samples(conn, "external", series(flux))
        end = T0 + timedelta(minutes=5 * len(flux))
        item = radiation.notice_item(conn, end)
        assert item["id"] == "radiation_recovery" and item["level"] == "ok"
        assert radiation.notice_item(conn, end + timedelta(hours=7)) is None or radiation.notice_item(conn, end + timedelta(hours=7))["id"] != "radiation_recovery"


# ---------- career limit, daily exposure and the sample week ----------
def test_default_limit_is_nasas_600_msv_career_limit(env):
    c, _, _ = env
    b = c.get("/api/radiation/budget?source=external").get_json()
    assert b["budget_msv"] == 600 == radiation.CAREER_LIMIT_MSV and b["initial_msv"] == 36.5
    assert "V1 4030" in b["limit_name"] and "600 mSv" in " ".join(b["assumptions"])


def test_daily_exposure_is_background_until_an_event_adds_dose(env):
    c, _, _ = env
    quiet = c.post("/api/radiation/simulate?source=simulated", json={"scenario": "quiet"}) and c.get("/api/radiation/budget?source=simulated").get_json()
    assert quiet["daily_exposure_msv"] == quiet["daily_background_msv"] and 0.5 * 0.65 - 0.001 <= quiet["daily_background_msv"] <= 0.5 * 1.35 + 0.001 and quiet["daily_event_msv_24h"] == 0
    c.post("/api/radiation/simulate?source=simulated", json={"scenario": "s4"})
    storm = c.get("/api/radiation/budget?source=simulated").get_json()
    assert storm["daily_event_msv_24h"] == 20 and storm["daily_exposure_msv"] > 20.3      # a dramatic jump only because of the event
    assert len(storm["daily"]) == 7 and storm["daily"][-1]["event_msv"] == 20 and storm["daily"][0]["event_msv"] == 0


def test_real_noaa_data_never_changes_the_dose(env):
    c, _, _ = env
    b = c.get("/api/radiation/budget?source=external").get_json()
    assert b["daily_event_msv_24h"] == 0 and b["event_dose_msv"] == 0                        # flux is never turned into dose


def test_sample_week_has_three_past_events_and_a_quiet_present(env):
    c, _, _ = env
    assert c.post("/api/radiation/simulate?source=simulated", json={"scenario": "history"}).get_json()["samples"] == 2016
    events = c.get("/api/radiation/events?source=simulated&days=7").get_json()["events"]
    assert sorted(e["s_class_peak"] for e in events) == [1, 1, 2] and not any(e["active"] for e in events)
    assert c.get("/api/radiation/status?source=simulated").get_json()["state"]["level"] == 0
    b = c.get("/api/radiation/budget?source=simulated").get_json()
    assert b["daily_exposure_msv"] < 1 and b["event_dose_msv"] == 1.2                      # 0.1 + 1.0 + 0.1 illustrative demo doses


def test_daily_background_varies_from_day_to_day_but_is_stable_for_a_day(env):
    c, _, _ = env
    first = c.get("/api/radiation/budget?source=simulated").get_json()
    values = [d["background_msv"] for d in first["daily"]]
    assert len(set(values)) > 3 and all(0.5 * 0.65 - 0.001 <= v <= 0.5 * 1.35 + 0.001 for v in values)
    assert c.get("/api/radiation/budget?source=simulated").get_json()["daily"] == first["daily"]       # reloading does not reshuffle


def test_demo_mission_days_left_and_projection(env):
    c, _, _ = env
    m = c.get("/api/radiation/budget?source=external").get_json()["mission"]
    assert m["assumed"] and m["days_total"] == 180 and m["day_now"] == 73 and m["days_left"] == 107
    assert m["projected_total_msv"] == pytest.approx(36.5 + 107 * 0.5, abs=0.2) and m["within_limit"] is True
    c.post("/api/radiation/budget?source=external", json={"mission_days": 400, "mission_day": 390})
    assert c.get("/api/radiation/budget?source=external").get_json()["mission"]["days_left"] == 10
    c.post("/api/radiation/budget?source=external", json={"mission_days": 100, "mission_day": 150})
    assert c.get("/api/radiation/budget?source=external").get_json()["mission"]["days_left"] == 0

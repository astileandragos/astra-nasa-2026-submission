"""Read-only analysis of stored data (docs/api_contract.md section 6.7).

Everything here is descriptive statistics of the person's own data. There are no medical
thresholds. Every function looks at ONE source at a time, so sources are never mixed.
Only readings with signal_quality "good" and a non-null value are used; null is never 0.
"""
import math
import statistics
import threading
import time
from datetime import date as date_type
from datetime import datetime, timedelta

# Documented parameters (shown to the user in the API answers).
MIN_PER_DAY = 20   # good readings a day needs to count towards the baseline
MIN_DAYS = 3       # days needed for a baseline
MIN_TODAY = 10     # good readings today needed for an observation
K = 2.0            # limit = K x the person's own standard deviation
HR_FLOOR = 1.0     # bpm: never flag differences smaller than the reading resolution
SPO2_FLOOR = 1.0   # percentage points: never flag differences smaller than the reading resolution
SLEEP_FLOOR = 0.5  # hours: the step of the check-in form
DISCLAIMER = "Educational prototype. This is not a diagnosis or medical advice."

READ = ("received_at, heart_rate_bpm, spo2_percent, signal_quality, "
        "accel_x_g, accel_y_g, accel_z_g")


def today_local():
    return datetime.now().astimezone().date().isoformat()


def _day(date_text):
    return date_type.fromisoformat(date_text)


def date_range(last_date, days):
    """Date strings, oldest first, ending at last_date."""
    end = _day(last_date)
    return [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


# ---- reuse of heavy answers ----
# Several pages ask for the same analysis every few seconds (notifications, observation, rest, wear, timeline). Computing it
# takes a few hundred milliseconds of Python on thousands of readings, so concurrent requests used to pile up and slow the
# server to a crawl. Now the answer is computed once, by one thread at a time, and reused for MEMO_TTL_S seconds.
# Only the live server turns this on (MEMO_BY_TIME_ONLY): an answer may then be up to MEMO_TTL_S old even if a reading just
# arrived. A new check-in or new radiation data always gives a new answer. Tests leave it off, so nothing is reused there.
MEMO_TTL_S = 3
MEMO_BY_TIME_ONLY = False
_memo = {}
_memo_lock = threading.RLock()


def data_version(conn):
    parts = [conn.execute("SELECT COUNT(*), COALESCE(MAX(received_at), '') FROM journal").fetchone()[:],
             conn.execute("SELECT COUNT(*), COALESCE(SUM(flux_pfu), 0), COALESCE(MAX(time_tag), '') FROM radiation_samples").fetchone()[:],
             conn.execute("SELECT COUNT(*) FROM radiation_ack").fetchone()[:],
             conn.execute("SELECT COALESCE(MAX(value), '') FROM radiation_meta WHERE key = 'simulated_scenario'").fetchone()[:]]
    return tuple(map(tuple, parts))


def memo(conn, key, compute):
    if not MEMO_BY_TIME_ONLY:
        return compute()
    full = (key, int(time.time() // MEMO_TTL_S), data_version(conn))
    with _memo_lock:
        if full in _memo:
            return _memo[full]
        if len(_memo) > 300:
            _memo.clear()
        value = _memo[full] = compute()
        return value


DASHBOARD = "dashboard"
# The dashboard reads one combined view: the earlier days come from the pre-recorded SIMULATED baseline week and today
# comes from the LIVE sensor (or, if no live reading arrived today, from the simulator). Each reading keeps its own
# label in the database; the dashboard says which part is which.


def today_source(conn):
    """Where today's readings come from in the dashboard view: live_hardware if any arrived today, else simulated."""
    row = conn.execute("SELECT 1 FROM measurements WHERE source = 'live_hardware' AND substr(received_at, 1, 10) = ? LIMIT 1",
                       (today_local(),)).fetchone()
    return "live_hardware" if row else "simulated"


def source_where(conn, source):
    """SQL condition (and its parameters) that picks the measurements of `source`; DASHBOARD is the combined view."""
    if source != DASHBOARD:
        return "source = ?", [source]
    today = today_local()
    return ("((source = 'simulated' AND substr(received_at, 1, 10) < ?) "
            "OR (source = ? AND substr(received_at, 1, 10) >= ?))"), [today, today_source(conn), today]


def _rows(conn, source, first, last):
    where, params = source_where(conn, source)
    return conn.execute(
        f"SELECT {READ} FROM measurements WHERE {where} "
        "AND substr(received_at, 1, 10) BETWEEN ? AND ? ORDER BY received_at",
        (*params, first, last)).fetchall()


def _good(rows, column):
    """Values of `column` from good-quality readings, grouped by date."""
    by_day = {}
    for r in rows:
        if r["signal_quality"] == "good" and r[column] is not None:
            by_day.setdefault(r["received_at"][:10], []).append(r[column])
    return by_day


def _clean(x, digits=1):
    if x is None:
        return None
    x = round(x, digits)
    return int(x) if x == int(x) else x


def _summary(values):
    if not values:
        return {"min": None, "max": None, "avg": None, "median": None, "n": 0}
    return {"min": _clean(min(values)), "max": _clean(max(values)),
            "avg": _clean(sum(values) / len(values)), "median": _clean(statistics.median(values)),
            "n": len(values)}


def quality(conn, source, last_date, days):
    dates = date_range(last_date, days)
    rows = _rows(conn, source, dates[0], dates[-1])
    counts = {"good": 0, "poor": 0, "no_finger": 0, "unknown": 0}
    per_day = {d: {"date": d, "total": 0, "good": 0, "missing_heart_rate": 0} for d in dates}
    missing = {"heart_rate_bpm": 0, "spo2_percent": 0, "motion": 0}
    for r in rows:
        counts[r["signal_quality"]] = counts.get(r["signal_quality"], 0) + 1
        day = per_day[r["received_at"][:10]]
        day["total"] += 1
        day["good"] += r["signal_quality"] == "good"
        if r["heart_rate_bpm"] is None:
            missing["heart_rate_bpm"] += 1
            day["missing_heart_rate"] += 1
        if r["spo2_percent"] is None:
            missing["spo2_percent"] += 1
        if None in (r["accel_x_g"], r["accel_y_g"], r["accel_z_g"]):
            missing["motion"] += 1
    where, params = source_where(conn, source)
    last = conn.execute(f"SELECT MAX(received_at) FROM measurements WHERE {where}", params).fetchone()[0]
    total = len(rows)
    return {"source": source, "date": last_date, "days": days, "total": total,
            "signal_quality": counts, "missing": missing,
            "good_share": round(counts["good"] / total, 3) if total else None,
            "last_received_at": last, "per_day": list(per_day.values())}


def daily_stats(conn, source, last_date, days):
    dates = date_range(last_date, days)
    rows = _rows(conn, source, dates[0], dates[-1])
    hr, spo2 = _good(rows, "heart_rate_bpm"), _good(rows, "spo2_percent")
    return {"source": source, "date": last_date, "days": days,
            "per_day": [{"date": d, "heart_rate_bpm": _summary(hr.get(d, [])),
                         "spo2_percent": _summary(spo2.get(d, []))} for d in dates]}


def _journal_source(source):
    return "simulated" if source == "simulated" else "self_reported"


def journal_where(source):
    """Check-ins: one per date, so the dashboard view simply reads all of them."""
    return ("1 = 1", []) if source == DASHBOARD else ("source = ?", [_journal_source(source)])


def _earlier_sleep(conn, source, last_date, days):
    first = date_range(last_date, days + 1)[0]
    where, params = journal_where(source)
    rows = conn.execute(
        f"SELECT date, sleep_hours FROM journal WHERE {where} AND date >= ? AND date < ? "
        "AND sleep_hours IS NOT NULL ORDER BY date", (*params, first, last_date)).fetchall()
    return [r["sleep_hours"] for r in rows]


def baseline(conn, source, last_date, days):
    previous = date_range(last_date, days + 1)[:-1]  # the days before last_date
    rows = _rows(conn, source, previous[0], previous[-1])
    hr_by_day = _good(rows, "heart_rate_bpm")
    spo2_by_day = _good(rows, "spo2_percent")
    usable = [d for d in previous if len(hr_by_day.get(d, [])) >= MIN_PER_DAY]
    sleep = _earlier_sleep(conn, source, last_date, days)
    out = {
        "source": source, "date": last_date,
        "method": (f"median of good-quality heart_rate_bpm readings on the previous days; a day needs "
                   f"{MIN_PER_DAY}+ good readings, {MIN_DAYS}+ days required"),
        "ready": len(usable) >= MIN_DAYS, "days_used": len(usable),
        "readings_used": sum(len(hr_by_day[d]) for d in usable),
        "heart_rate_bpm": None, "spo2_percent": None,
        "sleep_hours": ({"mean": _clean(sum(sleep) / len(sleep)), "n": len(sleep)}
                        if len(sleep) >= MIN_DAYS else None),
    }
    if not out["ready"]:
        out["reason"] = (f"not enough data yet: {len(usable)} of the {MIN_DAYS} days needed have "
                         f"{MIN_PER_DAY}+ good readings")
        return out
    pooled = [v for d in usable for v in hr_by_day[d]]
    q1, _, q3 = statistics.quantiles(pooled, n=4)
    out["heart_rate_bpm"] = {"median": _clean(statistics.median(pooled)), "q1": _clean(q1), "q3": _clean(q3),
                             "daily_medians": [_clean(statistics.median(hr_by_day[d])) for d in usable]}
    spo2 = [v for d in usable for v in spo2_by_day.get(d, [])]
    spo2_days = [d for d in usable if spo2_by_day.get(d)]
    out["spo2_percent"] = ({"median": _clean(statistics.median(spo2)),
                            "daily_medians": [_clean(statistics.median(spo2_by_day[d])) for d in spo2_days]}
                           if spo2 else None)
    out["_usable_days"] = usable  # internal, removed by the caller
    return out


def observation(conn, source, last_date, days=7):
    base = baseline(conn, source, last_date, days)
    usable = base.pop("_usable_days", [])
    result = {"source": source, "date": last_date, "status": "ok",
              "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "observations": [], "disclaimer": DISCLAIMER}
    today_rows = _rows(conn, source, last_date, last_date)
    today_hr = _good(today_rows, "heart_rate_bpm").get(last_date, [])

    if base["ready"] and len(today_hr) >= MIN_TODAY:
        medians = base["heart_rate_bpm"]["daily_medians"]
        sd = statistics.stdev(medians)
        limit = max(K * sd, HR_FLOOR)
        today_median = statistics.median(today_hr)
        diff = today_median - base["heart_rate_bpm"]["median"]
        notable = abs(diff) > limit
        word = "higher" if diff > 0 else "lower"
        message = (f"Today's median heart rate ({_clean(today_median)} bpm) is {word} than your baseline "
                   f"({base['heart_rate_bpm']['median']} bpm)." if notable else
                   f"Today's median heart rate ({_clean(today_median)} bpm) is within your usual variation "
                   f"(baseline {base['heart_rate_bpm']['median']} bpm).")
        obs = {"id": "hr_vs_baseline", "level": "notable" if notable else "info", "message": message,
               "based_on": {"metric": "heart_rate_bpm", "today_median": _clean(today_median),
                            "baseline_median": base["heart_rate_bpm"]["median"], "difference": _clean(diff),
                            "limit": _clean(limit), "readings_today": len(today_hr),
                            "baseline_days": base["days_used"],
                            "period": {"from": usable[0], "to": usable[-1]}},
               "rule": (f"notable when |today median - baseline median| is more than {K:g} x the standard "
                        "deviation of your own daily medians (at least 1 bpm)")}
        if notable:
            obs["suggested_step"] = ("Add a note about sleep, activity or stress to the daily check-in "
                                     "for context.")
        result["observations"].append(obs)

    # SpO2 uses the same rule as heart rate: today's median against the person's own baseline median, with the
    # limit set by the person's own day-to-day variation (at least SPO2_FLOOR). Needs enough good readings.
    today_spo2 = _good(today_rows, "spo2_percent").get(last_date, [])
    spo2_base = base.get("spo2_percent")
    if spo2_base and len(spo2_base["daily_medians"]) >= MIN_DAYS and len(today_spo2) >= MIN_TODAY:
        sd = statistics.stdev(spo2_base["daily_medians"])
        limit = max(K * sd, SPO2_FLOOR)
        today_median = statistics.median(today_spo2)
        diff = today_median - spo2_base["median"]
        notable = abs(diff) > limit
        word = "higher" if diff > 0 else "lower"
        message = (f"Today's median SpO2 estimate ({_clean(today_median)}%) is {word} than your baseline "
                   f"({spo2_base['median']}%)." if notable else
                   f"Today's median SpO2 estimate ({_clean(today_median)}%) is within your usual variation "
                   f"(baseline {spo2_base['median']}%).")
        result["observations"].append(
            {"id": "spo2_vs_baseline", "level": "notable" if notable else "info", "message": message,
             "based_on": {"metric": "spo2_percent", "today_median": _clean(today_median),
                          "baseline_median": spo2_base["median"], "difference": _clean(diff),
                          "limit": _clean(limit), "readings_today": len(today_spo2),
                          "baseline_days": len(spo2_base["daily_medians"]),
                          "period": {"from": usable[0], "to": usable[-1]}},
             "rule": (f"notable when |today median - baseline median| is more than {K:g} x the standard "
                      f"deviation of your own daily medians (at least {SPO2_FLOOR:g} percentage point)")})

    j_where, j_params = journal_where(source)
    sleep_today = conn.execute(
        f"SELECT sleep_hours FROM journal WHERE {j_where} AND date = ? AND sleep_hours IS NOT NULL",
        (*j_params, last_date)).fetchone()
    earlier = _earlier_sleep(conn, source, last_date, days)
    if sleep_today and len(earlier) >= MIN_DAYS:
        mean, sd = statistics.mean(earlier), statistics.stdev(earlier)
        limit = max(K * sd, SLEEP_FLOOR)
        diff = sleep_today["sleep_hours"] - mean
        notable = abs(diff) > limit
        word = "more" if diff > 0 else "less"
        message = (f"Reported sleep ({_clean(sleep_today['sleep_hours'])} h) is {word} than your average "
                   f"({_clean(mean)} h)." if notable else
                   f"Reported sleep ({_clean(sleep_today['sleep_hours'])} h) is within your usual variation "
                   f"(average {_clean(mean)} h).")
        obs = {"id": "sleep_vs_average", "level": "notable" if notable else "info", "message": message,
               "based_on": {"metric": "sleep_hours", "today": _clean(sleep_today["sleep_hours"]),
                            "average": _clean(mean), "difference": _clean(diff), "limit": _clean(limit),
                            "earlier_entries": len(earlier)},
               "rule": (f"notable when |reported sleep - your average| is more than {K:g} x the standard "
                        "deviation of your earlier entries (at least 0.5 h)")}
        if notable:
            obs["suggested_step"] = "Compare it with how you rate your energy and fatigue in the daily check-in."
        result["observations"].append(obs)

    import rest  # imported here because rest.py uses this module's helpers
    rest_obs = rest.observation_item(conn, source, last_date)
    if rest_obs:
        result["observations"].append(rest_obs)
    length_obs = rest.length_item(conn, source, last_date)
    if length_obs:
        result["observations"].append(length_obs)

    if not result["observations"]:
        result["status"] = "insufficient_data"
        reasons = []
        if not base["ready"]:
            reasons.append(base["reason"])
        elif len(today_hr) < MIN_TODAY:
            reasons.append(f"only {len(today_hr)} good heart rate readings today, {MIN_TODAY} needed")
        result["reason"] = "; ".join(reasons) or "no rule could be applied to the available data"
    return result


_observation_raw = observation


def observation(conn, source, last_date, days=7):
    return memo(conn, ("observation", source, last_date, days), lambda: _observation_raw(conn, source, last_date, days))


def activity(conn, source, last_date, window_min):
    rows = _rows(conn, source, last_date, last_date)
    buckets = {}
    for r in rows:
        ax, ay, az = r["accel_x_g"], r["accel_y_g"], r["accel_z_g"]
        if None in (ax, ay, az):
            continue
        minutes = int(r["received_at"][11:13]) * 60 + int(r["received_at"][14:16])
        start = minutes // window_min * window_min
        buckets.setdefault(start, []).append(abs(math.sqrt(ax * ax + ay * ay + az * az) - 1.0))
    windows = []
    for start in range(0, 24 * 60, window_min):
        values = buckets.get(start, [])
        windows.append({"start": f"{start // 60:02d}:{start % 60:02d}",
                        "movement_index": round(sum(values) / len(values), 3) if values else None,
                        "n": len(values)})
    return {"source": source, "date": last_date, "window_min": window_min, "windows": windows}


def timeline(conn, source, last_date, days):
    return memo(conn, ("timeline", source, last_date, days), lambda: _timeline_raw(conn, source, last_date, days))


def _timeline_raw(conn, source, last_date, days):
    """One row per day combining sensor data, movement and the self-reported check-in (read only).

    Sources stay separate: measurements come from `source`, the check-in from the matching journal source.
    """
    dates = date_range(last_date, days)
    rows = _rows(conn, source, dates[0], dates[-1])
    hr = _good(rows, "heart_rate_bpm")
    movement = {}
    count = {d: 0 for d in dates}
    for r in rows:
        day = r["received_at"][:10]
        count[day] += 1
        ax, ay, az = r["accel_x_g"], r["accel_y_g"], r["accel_z_g"]
        if None not in (ax, ay, az):
            movement.setdefault(day, []).append(abs(math.sqrt(ax * ax + ay * ay + az * az) - 1.0))
    checkins = {}
    j_where, j_params = journal_where(source)
    for e in conn.execute(
            f"SELECT date, sleep_hours, mood, energy, stress, fatigue, source FROM journal "
            f"WHERE {j_where} AND date BETWEEN ? AND ?", (*j_params, dates[0], dates[-1])):
        checkins[e["date"]] = dict(e)
    base = baseline(conn, source, last_date, 7)
    base.pop("_usable_days", None)
    hr_base = base["heart_rate_bpm"]
    per_day = []
    for d in dates:
        values = hr.get(d, [])
        per_day.append({
            "date": d, "readings": count[d],
            "heart_rate_bpm": {"median": _clean(statistics.median(values)) if values else None, "n": len(values)},
            "movement_index": round(sum(movement[d]) / len(movement[d]), 3) if d in movement else None,
            "checkin": checkins.get(d),
        })
    return {"source": source, "date": last_date, "days": days,
            "baseline": ({"median": hr_base["median"], "q1": hr_base["q1"], "q3": hr_base["q3"],
                          "days_used": base["days_used"]} if base["ready"] else None),
            "per_day": per_day}

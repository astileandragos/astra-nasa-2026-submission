"""Rest, rest regularity and wear time (docs/api_contract.md sections 6.12 and 6.13). Read only.

Rest is found from the ICM-20948 movement alone: it is NOT sleep staging and NOT a sleep diagnosis.
A 30 minute window is "still" when almost all of its motion readings are close to 1 g. The longest
stretch of still windows in the night is the rest period; a single moving window inside it is counted
as one wake-up. Every number is a descriptive statistic of the person's own data. There are no medical
thresholds, only the documented technical parameters below. One data source per answer; null is never 0.
"""
import math
import statistics
from datetime import datetime

import analysis

WINDOW_MIN = 30          # minutes per window
NIGHT_FROM = 18          # the night ending on day D starts at 18:00 on D-1 ...
NIGHT_TO = 12            # ... and ends at 12:00 on D
WINDOWS = (24 - NIGHT_FROM + NIGHT_TO) * 60 // WINDOW_MIN   # 36 windows
STILL_G = 0.05           # a reading is "still" when |acceleration magnitude - 1 g| is below this
STILL_SHARE = 0.8        # a window is "still" when this share of its motion readings are still
MIN_WINDOW_READINGS = 2  # motion readings a window needs, otherwise it counts as "no data"
MIN_RUN_WINDOWS = 4      # a rest period has at least 4 still windows (2 hours)
MIN_COVERAGE = 0.75      # share of the night's windows that must have data
START_FLOOR_MIN = 30     # minutes: never flag differences smaller than one window
MIN_NIGHTS = 3           # earlier nights needed for "usual" values
WEAR_OK = 0.8            # share of a day's windows with data that counts as "enough for trends"

DISCLAIMER = analysis.DISCLAIMER


def _hhmm(minutes_since_night_from):
    total = round(NIGHT_FROM * 60 + minutes_since_night_from) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def _window_of(received_at, date):
    """Index (0..35) of the night window a timestamp falls in for the night ending on `date`, or None."""
    day, hour, minute = received_at[:10], int(received_at[11:13]), int(received_at[14:16])
    minutes = hour * 60 + minute
    if day == date and hour < NIGHT_TO:
        return (24 * 60 - NIGHT_FROM * 60 + minutes) // WINDOW_MIN
    if day != date and hour >= NIGHT_FROM:
        return (minutes - NIGHT_FROM * 60) // WINDOW_MIN
    return None


def _best_run(states):
    """Longest run of still windows; one moving window between two still windows is a wake-up."""
    best = None
    i, n = 0, len(states)
    while i < n:
        if states[i] != "still":
            i += 1
            continue
        first = last = i
        wake, k = 0, i + 1
        while k < n:
            if states[k] == "still":
                last = k
                k += 1
            elif states[k] == "moving" and k + 1 < n and states[k + 1] == "still":
                wake += 1
                k += 1
            else:
                break
        still = sum(1 for s in states[first:last + 1] if s == "still")
        if still >= MIN_RUN_WINDOWS and (best is None or still > best["still"]):
            best = {"first": first, "last": last, "wake_ups": wake, "still": still}
        i = k
    return best


def night(conn, source, date):
    """The rest period of the night ending on `date` (18:00 the day before to 12:00)."""
    previous = analysis.date_range(date, 2)[0]
    motion = [[] for _ in range(WINDOWS)]
    heart = [[] for _ in range(WINDOWS)]
    for r in analysis._rows(conn, source, previous, date):
        w = _window_of(r["received_at"], date)
        if w is None:
            continue
        ax, ay, az = r["accel_x_g"], r["accel_y_g"], r["accel_z_g"]
        if None not in (ax, ay, az):
            motion[w].append(abs(math.sqrt(ax * ax + ay * ay + az * az) - 1.0))
        if r["signal_quality"] == "good" and r["heart_rate_bpm"] is not None:
            heart[w].append(r["heart_rate_bpm"])
    states = []
    for values in motion:
        if len(values) < MIN_WINDOW_READINGS:
            states.append("no_data")
        else:
            still = sum(1 for v in values if v < STILL_G) / len(values)
            states.append("still" if still >= STILL_SHARE else "moving")
    coverage = round(sum(1 for s in states if s != "no_data") / WINDOWS, 2)
    out = {"date": date, "status": "insufficient_data", "coverage": coverage, "rest_start": None,
           "rest_end": None, "start_minutes": None, "duration_h": None, "wake_ups": None,
           "resting_heart_rate": None}
    if coverage < MIN_COVERAGE:
        out["reason"] = (f"only {round(coverage * 100)}% of the night has motion readings, "
                         f"{round(MIN_COVERAGE * 100)}% needed")
        return out
    run = _best_run(states)
    if run is None:
        out["reason"] = f"no still period of {MIN_RUN_WINDOWS * WINDOW_MIN // 60} hours or more found"
        return out
    resting = [v for w in range(run["first"], run["last"] + 1) if states[w] == "still" for v in heart[w]]
    start = run["first"] * WINDOW_MIN
    end = (run["last"] + 1) * WINDOW_MIN
    out.update({"status": "ok", "start_minutes": start, "rest_start": _hhmm(start), "rest_end": _hhmm(end),
                "duration_h": analysis._clean((end - start) / 60), "wake_ups": run["wake_ups"],
                "resting_heart_rate": ({"median": analysis._clean(statistics.median(resting)), "n": len(resting)}
                                       if resting else None)})
    out.pop("reason", None)
    return out


def _usual(earlier):
    """Usual rest start and end (median) and spread (standard deviation, minutes) of earlier nights."""
    starts = [n["start_minutes"] for n in earlier]
    ends = [n["start_minutes"] + round(n["duration_h"] * 60) for n in earlier]
    return {"nights_used": len(earlier),
            "start_median": _hhmm(statistics.median(starts)),
            "start_spread_min": analysis._clean(statistics.stdev(starts)),
            "start_range_min": max(starts) - min(starts),
            "end_median": _hhmm(statistics.median(ends)),
            "end_spread_min": analysis._clean(statistics.stdev(ends))}


def rest(conn, source, date, nights):
    return analysis.memo(conn, ("rest", source, date, nights), lambda: _rest_raw(conn, source, date, nights))


def _rest_raw(conn, source, date, nights):
    dates = analysis.date_range(date, nights)
    items = [night(conn, source, d) for d in dates]
    good = [n for n in items if n["status"] == "ok"]
    earlier = [n for n in good if n["date"] != date]
    return {
        "source": source, "date": date, "nights": nights,
        "method": (f"motion from the ICM-20948 in {WINDOW_MIN} minute windows between {NIGHT_FROM}:00 and "
                   f"{NIGHT_TO}:00; a window is still when {round(STILL_SHARE * 100)}% of its readings are "
                   f"within {STILL_G} g of 1 g; rest = the longest still stretch of at least "
                   f"{MIN_RUN_WINDOWS * WINDOW_MIN // 60} hours; one moving window inside it = one wake-up"),
        "limits": ("An experimental estimate from movement only. It does not measure sleep stages and is "
                   "not a diagnosis. A night needs motion readings for at least "
                   f"{round(MIN_COVERAGE * 100)}% of its windows."),
        "per_night": items,
        "usual": _usual(earlier) if len(earlier) >= MIN_NIGHTS else None,
        "disclaimer": DISCLAIMER,
    }


LENGTH_FLOOR_MIN = 45    # minutes: never flag a difference in rest length smaller than this


def length_item(conn, source, date):
    """Observation: last night's rest length (from movement) against the person's earlier nights. None when it cannot be applied."""
    data = rest(conn, source, date, 8)
    last = data["per_night"][-1]
    earlier = [n for n in data["per_night"][:-1] if n["status"] == "ok"]
    if last["status"] != "ok" or len(earlier) < MIN_NIGHTS:
        return None
    lengths = [n["duration_h"] * 60 for n in earlier]
    usual = statistics.median(lengths)
    diff = last["duration_h"] * 60 - usual
    limit = max(analysis.K * statistics.stdev(lengths), LENGTH_FLOOR_MIN)
    notable = abs(diff) > limit
    word = "longer" if diff > 0 else "shorter"
    message = (f"Last night's rest was {last['duration_h']} h, {round(abs(diff))} minutes {word} than usual "
               f"({round(usual / 60, 1)} h)." if notable else
               f"Last night's rest was {last['duration_h']} h, within your usual variation ({round(usual / 60, 1)} h).")
    return {"id": "rest_length_vs_usual", "level": "notable" if notable else "info", "message": message,
            "based_on": {"metric": "rest_length", "last_night_h": last["duration_h"], "usual_h": analysis._clean(usual / 60),
                         "difference_min": analysis._clean(diff), "limit_min": analysis._clean(limit),
                         "earlier_nights": len(earlier)},
            "rule": (f"notable when |last night's rest length - your median rest length| is more than "
                     f"{analysis.K:g} x the standard deviation of your earlier rest lengths (at least {LENGTH_FLOOR_MIN} minutes). "
                     "Estimated from movement only; it is not a sleep measurement.")}


def observation_item(conn, source, date):
    """A rule-based observation for the observation endpoint, or None when it cannot be applied."""
    data = rest(conn, source, date, 8)
    last = data["per_night"][-1]
    earlier = [n for n in data["per_night"][:-1] if n["status"] == "ok"]
    if last["status"] != "ok" or len(earlier) < MIN_NIGHTS:
        return None
    starts = [n["start_minutes"] for n in earlier]
    usual = statistics.median(starts)
    diff = last["start_minutes"] - usual
    limit = max(analysis.K * statistics.stdev(starts), START_FLOOR_MIN)
    notable = abs(diff) > limit
    word = "later" if diff > 0 else "earlier"
    message = (f"Last night's rest started {round(abs(diff))} minutes {word} than usual ({_hhmm(usual)})."
               if notable else
               f"Last night's rest started within your usual variation (usual start {_hhmm(usual)}).")
    obs = {"id": "rest_start_vs_usual", "level": "notable" if notable else "info", "message": message,
           "based_on": {"metric": "rest_start", "last_night": last["rest_start"], "usual": _hhmm(usual),
                        "difference_min": analysis._clean(diff), "limit_min": analysis._clean(limit),
                        "earlier_nights": len(earlier)},
           "rule": (f"notable when |last night's rest start - your median rest start| is more than "
                    f"{analysis.K:g} x the standard deviation of your earlier rest starts "
                    f"(at least {START_FLOOR_MIN} minutes)")}
    if notable:
        obs["suggested_step"] = "Add a note about what changed to the daily check-in for context."
    return obs


def wear(conn, source, date, days, now_minutes=None):
    """Per day: how much of the day has data from the device (30 minute windows)."""
    if now_minutes is None:
        return analysis.memo(conn, ("wear", source, date, days), lambda: wear(conn, source, date, days, -1))
    if now_minutes == -1:
        now_minutes = None
    dates = analysis.date_range(date, days)
    rows = analysis._rows(conn, source, dates[0], dates[-1])
    if now_minutes is None:
        now = datetime.now().astimezone()
        now_minutes = now.hour * 60 + now.minute
    per_window = {d: {} for d in dates}     # date -> window -> [any reading, good heart rate]
    times = {d: [] for d in dates}
    for r in rows:
        d = r["received_at"][:10]
        minutes = int(r["received_at"][11:13]) * 60 + int(r["received_at"][14:16]) + int(r["received_at"][17:19]) / 60
        times[d].append(minutes)
        flags = per_window[d].setdefault(int(minutes) // WINDOW_MIN, [False, False])
        flags[0] = True
        if r["signal_quality"] == "good" and r["heart_rate_bpm"] is not None:
            flags[1] = True
    is_today = date == analysis.today_local()
    per_day = []
    for d in dates:
        last_minute = now_minutes if (is_today and d == date) else 24 * 60
        possible = max(1, math.ceil(last_minute / WINDOW_MIN))
        windows = per_window[d]
        data_w = sum(1 for f in windows.values() if f[0])
        hr_w = sum(1 for f in windows.values() if f[1])
        gap = None
        if times[d]:
            edges = [0.0, *sorted(times[d]), float(last_minute)]
            gap = analysis._clean(max(b - a for a, b in zip(edges, edges[1:])) / 60)
        coverage = round(min(1.0, data_w / possible), 2)
        per_day.append({"date": d, "readings": len(times[d]), "data_hours": analysis._clean(data_w * WINDOW_MIN / 60),
                        "heart_rate_hours": analysis._clean(hr_w * WINDOW_MIN / 60), "coverage": coverage,
                        "longest_gap_h": gap, "enough": coverage >= WEAR_OK})
    return {"source": source, "date": date, "days": days,
            "method": (f"a {WINDOW_MIN} minute window counts when it has at least one reading from this device; "
                       f"coverage = counted windows / windows of the day (today: until now); "
                       f"'enough' when coverage is at least {round(WEAR_OK * 100)}%"),
            "why": ("Results such as rest and the baseline can differ when the device is worn only part of the "
                    "time (NASA compared continuous and intermittent wear of activity monitors on long missions). "
                    "This view shows how complete each day is, so patchy days are not trusted blindly."),
            "per_day": per_day,
            "days_enough": sum(1 for p in per_day if p["enough"])}

"""Radiation Risk Monitor: solar proton event detection, alerts and an educational exposure budget.

Read docs/RADIATION_MONITOR.md first. The short version:
  * The input is the integral proton flux >= 10 MeV (pfu) measured by NOAA's GOES satellites ("external"),
    or a simulated scenario ("simulated"). It is a SPACE WEATHER measurement, not the dose inside a spacecraft.
  * NOAA's S-scale (S1 to S5, thresholds 10, 100, 1000, 10 000, 100 000 pfu) classifies the event.
  * A small, explainable state machine turns the flux samples into alert levels 0 to 3 (hysteresis, no duplicates).
    The state is computed by replaying the stored samples, so the same samples always give the same events and
    the same alert ids: a duplicate alert cannot exist.
  * The exposure budget is an ILLUSTRATIVE model (D_remaining = D_budget - D_accumulated, T = D_remaining / R).
    Dose is NEVER computed from proton flux. Dose entries come from a labelled simulation or from an operator.
  * Alert levels are demonstration interface states, not NASA flight rules.
"""
import json
import math
import threading
import urllib.request
from datetime import datetime, timedelta, timezone

CHANNEL = ">=10 MeV"
NOAA_BASE = "https://services.swpc.noaa.gov/json/goes/primary/"
NOAA_FILES = {"history": "integral-protons-1-day.json", "update": "integral-protons-6-hour.json"}
FETCH_TTL_S = 60            # NOAA serves these files with Cache-Control max-age=60
FETCH_TIMEOUT_S = 5
SOURCES = ("external", "simulated")
SOURCE_LABELS = {"external": "NOAA GOES (real external data)", "simulated": "Simulated scenario"}

# NOAA Space Radiation Storm scale: S class -> minimum >=10 MeV proton flux in pfu.
S_THRESHOLDS = [(1, 10.0), (2, 100.0), (3, 1000.0), (4, 10000.0), (5, 100000.0)]
S_NAMES = {0: "below S1", 1: "S1 Minor", 2: "S2 Moderate", 3: "S3 Strong", 4: "S4 Severe", 5: "S5 Extreme"}
LEVEL_NAMES = {0: "NORMAL", 1: "ELEVATED", 2: "HIGH", 3: "SEVERE"}

# Detection parameters (illustrative, documented in docs/RADIATION_MONITOR.md).
ONSET_SAMPLES = 3           # consecutive samples at or above S1 before an event starts (like SWPC's event list)
ESCALATE_SAMPLES = 2        # consecutive samples above the current level before escalating
EASE_SAMPLES = 6            # consecutive samples below the current level (30 min at 5 min) before easing
FALL_FACTOR = 0.5           # hysteresis: to count as "lower" a sample must be below half the threshold
GAP_RESET_MIN = 30          # a gap this long between samples restarts the consecutive-sample counters
DELAYED_AFTER_MIN = 15      # NOAA files lag about 10 minutes behind
STALE_AFTER_MIN = 120

# Illustrative demonstration doses (mSv) a simulated event adds to the budget. Chosen by the team for the demo.
# NOT derived from proton flux and NOT NASA values.
SIM_DOSE_MSV = {1: 0.1, 2: 1.0, 3: 5.0, 4: 20.0, 5: 60.0}
SCENARIOS = {"quiet": 0, "watch": 0, "prepare": 0, "s1": 1, "s2": 2, "s3": 3, "s4": 4, "history": 0}   # "history": a quiet week with three past events
SCENARIO_PEAK_PFU = {1: 40.0, 2: 400.0, 3: 4000.0, 4: 40000.0}

# The limit is NASA's career effective dose limit (NASA-STD-3001 Vol 1 [V1 4030], 600 mSv, universal for all ages and sexes).
# The dose already received is unknown to ASTRA, so it starts at 0 and is entered by the user. The background rate is an
# assumption (NASA's brief uses about 0.5 mSv/day for a surface mission; ISS crews get roughly 0.4 to 1.0 mSv/day).
CAREER_LIMIT_MSV = 600.0
# DEMO MISSION (assumed, "a random mission" for the moment): 180 days long and today is mission day 73, so the dose
# received so far starts at 73 x 0.5 = 36.5 mSv. All three are settings the user can change.
DAILY_VARIATION = 0.35      # each day's background varies by up to +/-35% around the average rate (simulated variation)
BUDGET_DEFAULTS = {"budget_msv": CAREER_LIMIT_MSV, "initial_msv": 36.5, "baseline_rate_msv_day": 0.5,
                   "mission_days": 180.0, "mission_day": 73.0}
BUDGET_LIMITS = {"budget_msv": (1.0, 5000.0), "initial_msv": (0.0, 5000.0), "baseline_rate_msv_day": (0.0, 10.0),
                 "mission_days": (1.0, 2000.0), "mission_day": (0.0, 2000.0)}

DISCLAIMER = ("Educational prototype. Alert levels and the exposure budget are demonstration models, not NASA flight rules "
              "and not a medically certified safe mission duration. ASTRA does not replace NASA's radiation monitoring.")

ALERT_TEXT = {
    1: {"summary": "Solar proton flux is at or above the S1 level.",
        "actions": ["Monitor the situation.", "Review mission conditions and planned activities.",
                    "Watch for updates on this page."],
        "oled": ["Monitor the situation", "Review conditions"], "beep": "short"},
    2: {"summary": "Solar proton flux is at the S2 or S3 level.",
        "actions": ["Avoid or postpone EVA activities.", "Be ready to go to the designated radiation shelter.",
                    "Wait for updated instructions."],
        "oled": ["No EVA. Be ready for", "shelter. Stand by."], "beep": "double"},
    3: {"summary": "Solar proton flux is at the S4 or S5 level.",
        "actions": ["Go to the designated radiation shelter immediately.", "Stay in the protected area.",
                    "Wait for mission control clearance before leaving."],
        "oled": ["SHELTER NOW", "Await mission ctrl"], "beep": "continuous"},
}


# ------------------------------------------------------------------ classification
def s_class(flux, factor=1.0):
    """NOAA S class (0 to 5) of a >= 10 MeV proton flux in pfu. `factor` scales the thresholds (hysteresis)."""
    cls = 0
    for number, threshold in S_THRESHOLDS:
        if flux >= threshold * factor:
            cls = number
    return cls


def alert_level(s):
    """ASTRA demonstration alert level from an S class: 0 normal, 1 elevated (S1), 2 high (S2, S3), 3 severe (S4, S5)."""
    return 0 if s == 0 else 1 if s == 1 else 2 if s <= 3 else 3


def _utc(text):
    """Parse an ISO time (with Z or an offset) into an aware UTC datetime."""
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _now(now):
    return now or datetime.now(timezone.utc)


# ------------------------------------------------------------------ NOAA data
def parse_noaa(records):
    """Keep the >= 10 MeV channel. Returns (samples, skipped). A sample is (utc_iso, flux, satellite).

    Missing, non-numeric, negative or non-finite values are skipped, never turned into 0.
    """
    samples, skipped = [], 0
    if not isinstance(records, list):
        raise ValueError("NOAA answer is not a list")
    for record in records:
        if not isinstance(record, dict) or record.get("energy") != CHANNEL:
            continue
        flux = record.get("flux")
        if isinstance(flux, bool) or not isinstance(flux, (int, float)) or not math.isfinite(flux) or flux < 0:
            skipped += 1
            continue
        try:
            when = _iso(_utc(record["time_tag"]))
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        satellite = record.get("satellite")
        samples.append((when, float(flux), satellite if isinstance(satellite, int) else None))
    return samples, skipped


def fetch_noaa(url):
    """Download one NOAA JSON file. Raises on any network or format problem."""
    request = urllib.request.Request(url, headers={"User-Agent": "ASTRA-educational-prototype"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as answer:
        return json.loads(answer.read().decode("utf-8"))


def _meta_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM radiation_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _meta_set(conn, key, value):
    conn.execute("INSERT INTO radiation_meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))


def refresh_external(conn, fetch=None, now=None):
    """Fetch NOAA proton flux and store the new samples. Never raises: failures are recorded and reported."""
    now = _now(now)
    fetch = fetch or fetch_noaa
    have = conn.execute("SELECT COUNT(*) FROM radiation_samples WHERE source = 'external'").fetchone()[0]
    name = NOAA_FILES["update" if have else "history"]
    result = {"inserted": 0, "skipped": 0, "error": None, "file": name}
    _meta_set(conn, "external_last_attempt", _iso(now))
    try:
        samples, skipped = parse_noaa(fetch(NOAA_BASE + name))
        result["skipped"] = skipped
        for when, flux, satellite in samples:
            cur = conn.execute("INSERT OR IGNORE INTO radiation_samples (source, time_tag, flux_pfu, satellite) "
                               "VALUES ('external', ?, ?, ?)", (when, flux, satellite))
            result["inserted"] += cur.rowcount
        _meta_set(conn, "external_last_fetch", _iso(now))
        _meta_set(conn, "external_last_error", "")
    except Exception as error:                      # network down, bad JSON, timeout: keep what we have
        result["error"] = f"{type(error).__name__}: {error}"[:200]
        _meta_set(conn, "external_last_error", result["error"])
    conn.commit()
    return result


def refresh_due(conn, now=None):
    last = _meta_get(conn, "external_last_attempt")
    return last is None or (_now(now) - _utc(last)).total_seconds() >= FETCH_TTL_S


_refresh_lock = threading.Lock()


def refresh_in_background(open_db, fetch=None):
    """Refresh NOAA data in a thread so a slow or missing network never blocks a dashboard request."""
    if not _refresh_lock.acquire(blocking=False):
        return False

    def work():
        try:
            conn = open_db()
            try:
                refresh_external(conn, fetch)
            finally:
                conn.close()
        finally:
            _refresh_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


# ------------------------------------------------------------------ samples
def load_samples(conn, source, hours=168, now=None):
    since = _iso(_now(now) - timedelta(hours=hours))
    rows = conn.execute("SELECT time_tag, flux_pfu FROM radiation_samples WHERE source = ? AND time_tag >= ? "
                        "ORDER BY time_tag", (source, since)).fetchall()
    return [(r["time_tag"], r["flux_pfu"]) for r in rows]


def data_status(samples, now=None):
    """ok, delayed, stale or no_data, from the age of the newest sample."""
    if not samples:
        return {"status": "no_data", "age_min": None}
    age = (_now(now) - _utc(samples[-1][0])).total_seconds() / 60
    age = max(0.0, age)
    status = "ok" if age <= DELAYED_AFTER_MIN else "delayed" if age <= STALE_AFTER_MIN else "stale"
    return {"status": status, "age_min": round(age, 1)}


# ------------------------------------------------------------------ event detection (the explainable part)
def _compact(moment_iso):
    return _utc(moment_iso).strftime("%Y%m%dT%H%M%SZ")


def _alert(source, event, seq, kind, level, s, flux, when):
    text = ALERT_TEXT[level] if level else ALERT_TEXT[event["level_max"]]
    if kind == "recovery":
        title, message, actions = ("Radiation back to normal", "The solar proton flux has stayed below S1 for 30 minutes.",
                                   ["Wait for mission control clearance before resuming EVA.",
                                    "Keep watching this page for new events."])
    elif kind == "easing":
        title, message, actions = (f"Radiation easing to level {level} ({LEVEL_NAMES[level]})",
                                   f"The flux has stayed lower for 30 minutes. {text['summary']}",
                                   ["Stay cautious until the level is normal.", *text["actions"][:1]])
    else:
        title = f"Radiation level {level} ({LEVEL_NAMES[level]})" + (" - escalated" if kind == "escalation" else "")
        message, actions = text["summary"], list(text["actions"])
    return {"id": f"{source}:{event['id'].split(':', 1)[1]}:{seq}", "source": source, "event_id": event["id"],
            "at": when, "kind": kind, "level": level, "s_class": s, "flux_pfu": round(flux, 3), "title": title,
            "message": message, "actions": actions, "requires_ack": kind in ("onset", "escalation"),
            "acknowledged_at": None}


def evaluate(samples, source):
    """Replay the samples through the state machine. Returns events, alerts and the current state.

    Rules (all counts are consecutive samples; a gap longer than GAP_RESET_MIN restarts the counters):
      onset      level 0 -> L    the last ONSET_SAMPLES samples are all at or above S1; L = the lowest of them
      escalate   L -> L' > L     the last ESCALATE_SAMPLES samples are all above L; L' = the lowest of them
      ease       L -> L' < L     the last EASE_SAMPLES samples are all lower than L when judged with thresholds x FALL_FACTOR
      recovery   L -> 0          the same, with L' = 0 (the event ends)
    """
    level, raw, fall, times, previous = 0, [], [], [], None
    events, alerts, event = [], [], None
    last_flux = last_time = None
    for when, flux in samples:
        moment = _utc(when)
        if previous is not None and (moment - previous).total_seconds() > GAP_RESET_MIN * 60:
            raw, fall, times = [], [], []
        previous = moment
        last_flux, last_time = flux, when
        raw.append(alert_level(s_class(flux)))
        fall.append(alert_level(s_class(flux, FALL_FACTOR)))
        times.append((when, flux))
        raw, fall, times = raw[-EASE_SAMPLES:], fall[-EASE_SAMPLES:], times[-EASE_SAMPLES:]
        if event is not None:
            event["peak_flux_pfu"] = max(event["peak_flux_pfu"], flux)
        new = level
        if level == 0:
            if len(raw) >= ONSET_SAMPLES and min(raw[-ONSET_SAMPLES:]) >= 1:
                new = min(raw[-ONSET_SAMPLES:])
        elif len(raw) >= ESCALATE_SAMPLES and min(raw[-ESCALATE_SAMPLES:]) > level:
            new = min(raw[-ESCALATE_SAMPLES:])
        elif len(fall) >= EASE_SAMPLES and max(fall[-EASE_SAMPLES:]) < level:
            new = max(fall[-EASE_SAMPLES:])
        if new == level:
            continue
        s_now = s_class(flux)
        if level == 0:                                       # onset: the event starts at the first sample of the run
            run = times[-ONSET_SAMPLES:]
            event = {"id": f"{source}:{_compact(run[0][0])}", "source": source, "started_at": run[0][0],
                     "ended_at": None, "peak_flux_pfu": max(f for _, f in run), "level_max": new, "alert_count": 0}
            events.append(event)
            kind, seq = "onset", 1
        elif new > level:
            kind, seq = "escalation", event["alert_count"] + 1
        elif new > 0:
            kind, seq = "easing", event["alert_count"] + 1
        else:
            kind, seq = "recovery", event["alert_count"] + 1
            event["ended_at"] = times[-EASE_SAMPLES][0]
        event["alert_count"] = seq
        event["level_max"] = max(event["level_max"], new)
        alerts.append(_alert(source, event, seq, kind, new, s_now, flux, when))
        if new == 0:
            event = None
        level = new
    for item in events:
        item["s_class_peak"] = s_class(item["peak_flux_pfu"])
        item["peak_flux_pfu"] = round(item["peak_flux_pfu"], 3)
        item["active"] = item["ended_at"] is None
        item["duration_min"] = (round((_utc(item["ended_at"] or last_time) - _utc(item["started_at"])).total_seconds() / 60)
                                if last_time else None)
    active = next((e for e in events if e["active"]), None)
    state = {"level": level, "level_name": LEVEL_NAMES[level],
             "s_class_now": s_class(last_flux) if last_flux is not None else None,
             "flux_pfu": round(last_flux, 3) if last_flux is not None else None, "last_sample_at": last_time,
             "event_id": active["id"] if active else None, "event_started_at": active["started_at"] if active else None,
             "s_class_peak": active["s_class_peak"] if active else None}
    return {"events": events, "alerts": alerts, "state": state}


def _apply_acks(conn, alerts):
    acked = {r["alert_id"]: r["acknowledged_at"] for r in conn.execute("SELECT alert_id, acknowledged_at FROM radiation_ack")}
    for item in alerts:
        item["acknowledged_at"] = acked.get(item["id"])
    return alerts


def analysis(conn, source, now=None, hours=168):
    now = _now(now)
    samples = load_samples(conn, source, hours, now)
    result = evaluate(samples, source)
    _apply_acks(conn, result["alerts"])
    result["data"] = data_status(samples, now)
    result["samples"] = samples
    return result


def ack_pending(result):
    """The newest alert that asks for an acknowledgement and has none, while an event is active."""
    if result["state"]["level"] == 0:
        return None
    for item in reversed(result["alerts"]):
        if item["requires_ack"]:
            return item if item["acknowledged_at"] is None else None
    return None


def acknowledge(conn, alert_id, now=None):
    """Acknowledge a known alert. Returns the alert or None. Acknowledging does not change the level."""
    for source in SOURCES:
        for item in evaluate(load_samples(conn, source, 168, now), source)["alerts"]:
            if item["id"] == alert_id:
                conn.execute("INSERT OR IGNORE INTO radiation_ack (alert_id, acknowledged_at) VALUES (?, ?)",
                             (alert_id, _iso(_now(now))))
                conn.commit()
                item["acknowledged_at"] = conn.execute("SELECT acknowledged_at FROM radiation_ack WHERE alert_id = ?",
                                                       (alert_id,)).fetchone()[0]
                return item
    return None


# ------------------------------------------------------------------ OLED text for the ESP32
def _flux_text(flux):
    return "--" if flux is None else f"{flux:.0f}" if flux >= 10 else f"{flux:.2f}"


def oled(result, source, now=None):
    """What the ESP32 should show: 4 lines of at most 21 characters (SSD1306 128x64, 6x8 font), a footer, a beep pattern."""
    state, data = result["state"], result["data"]
    level, s = state["level"], state["s_class_now"]
    pending = ack_pending(result)
    clock = state["last_sample_at"][11:16] + "Z" if state["last_sample_at"] else "--:--"
    flux_line = f"S{s} {_flux_text(state['flux_pfu'])} pfu >=10MeV" if s is not None else "no data"
    if level == 0:
        lines = ["RADIATION: NORMAL", flux_line, ("NOAA " if source == "external" else "SIM ") + clock, "No action needed"]
        beep = "none"
    else:
        text = ALERT_TEXT[level]
        lines = [f"RAD {level} {LEVEL_NAMES[level]}", flux_line, *text["oled"]]
        beep = text["beep"] if pending else "none"
    footer = ("DATA DELAYED" if data["status"] == "delayed" else "DATA STALE" if data["status"] == "stale"
              else "NO DATA" if data["status"] == "no_data" else "BTN = ACKNOWLEDGE" if pending else "")
    return {"lines": [line[:21] for line in lines], "footer": footer, "beep": beep, "repeat_until_ack": bool(pending) and level >= 2}


# ------------------------------------------------------------------ status, history, notification
def status(conn, source, now=None):
    now = _now(now)
    result = analysis(conn, source, now)
    state, data = result["state"], result["data"]
    pending = ack_pending(result)
    level = state["level"]
    last_error = _meta_get(conn, "external_last_error", "") if source == "external" else ""
    return {
        "source": source, "label": source, "source_name": SOURCE_LABELS[source], "generated_at": _iso(now),
        "data_status": data["status"], "data_age_min": data["age_min"],
        "last_fetch_at": _meta_get(conn, "external_last_fetch") if source == "external" else None,
        "fetch_error": last_error or None,
        "state": state, "alert": ({"level": level, "name": LEVEL_NAMES[level], "summary": ALERT_TEXT[level]["summary"],
                                   "actions": ALERT_TEXT[level]["actions"]} if level else None),
        "ack_pending": {"alert_id": pending["id"], "title": pending["title"]} if pending else None,
        "oled": oled(result, source, now),
        "thresholds": [{"s_class": n, "name": S_NAMES[n], "flux_pfu": t, "alert_level": alert_level(n)} for n, t in S_THRESHOLDS],
        "what_it_is": ("Integral proton flux >= 10 MeV from NOAA's GOES satellites in geostationary orbit. It classifies "
                       "the space weather event. It is not the radiation dose inside a spacecraft."
                       if source == "external" else
                       "A simulated flux scenario for the demonstration. It is not a measurement."),
        "disclaimer": DISCLAIMER,
    }


def history(conn, source, hours, now=None):
    samples = load_samples(conn, source, hours, now)
    return {"source": source, "hours": hours, "channel": CHANNEL, "unit": "pfu",
            "samples": [{"time": t, "flux_pfu": round(f, 4), "s_class": s_class(f)} for t, f in samples],
            "thresholds": [{"s_class": n, "flux_pfu": t} for n, t in S_THRESHOLDS],
            "data_status": data_status(samples, now)["status"]}


def notice_item(conn, now=None):
    """A notification for the Overview, from stored data only (never fetches). None when there is nothing to say."""
    best = None
    for source in SOURCES:
        result = analysis(conn, source, now)
        if best is None or result["state"]["level"] > best[1]["state"]["level"]:
            best = (source, result)
    source, result = best
    level = result["state"]["level"]
    where = "simulated scenario" if source == "simulated" else "NOAA GOES"
    status = result["data"]["status"]
    last = result["state"].get("last_sample_at")
    if level == 0 and status in ("stale", "no_data"):
        when = f" The last data received is from {last[:16].replace('T', ' ')} UTC." if last else ""
        return {"id": "radiation_data", "level": "warning", "title": "Radiation data unavailable",
                "message": "Radiation data are temporarily unavailable." + when,
                "page": "radiation.html", "target": "rad-status-h",
                "advice": {"meaning": "Without current data ASTRA cannot say whether conditions are normal. Do not assume that they are.",
                           "steps": ["Check the data connection.", "Follow the mission's radiation procedures and mission control updates.",
                                     "Open the Radiation page to see the last information received."]}}
    if level == 0:
        recovery = [a for a in result["alerts"] if a["kind"] == "recovery"]
        if recovery and (_utc(_iso(_now(now))) - _utc(recovery[-1]["at"])).total_seconds() <= 6 * 3600:
            return {"id": "radiation_recovery", "level": "ok", "title": "Radiation event ended",
                    "message": f"The solar proton flux returned below S1 at {recovery[-1]['at'][11:16]} UTC ({where}).",
                    "page": "radiation.html", "target": "rad-status-h",
                    "advice": {"meaning": "The event has ended according to the demonstration rules. Mission control decides when normal activities resume.",
                               "steps": ["Wait for mission control clearance before resuming EVA."]}}
        if source != "external" or status != "ok":
            return None
        return {"id": "radiation", "level": "ok", "title": "Space radiation is normal",
                "message": f"Solar proton flux {_flux_text(result['state']['flux_pfu'])} pfu (NOAA GOES).",
                "page": "radiation.html", "target": "rad-status-h",
                "advice": {"meaning": "The solar proton flux is below the S1 level. This is space weather data, not the dose inside a spacecraft.",
                           "steps": []}}
    text = ALERT_TEXT[level]
    return {"id": "radiation", "level": "warning" if level == 1 else "danger",
            "title": f"Radiation level {level} ({LEVEL_NAMES[level]})",
            "message": f"S{result['state']['s_class_now']} event, {_flux_text(result['state']['flux_pfu'])} pfu ({where})."
                       + (" The data are not current: this is the last known level." if status in ("stale", "no_data") else ""),
            "page": "radiation.html", "target": "rad-status-h",
            "advice": {"meaning": text["summary"] + " Alert levels are demonstration states, not NASA flight rules; "
                       "follow mission control and the mission's own procedures.",
                       "steps": [*text["actions"], "Open the Radiation page for the event timeline and the exposure budget."]}}


# ------------------------------------------------------------------ events and alerts lists
def events_and_alerts(conn, source, days, now=None):
    result = analysis(conn, source, now, hours=max(24, days * 24))
    return {"source": source, "days": days, "events": list(reversed(result["events"])),
            "alerts": list(reversed(result["alerts"])), "data_status": result["data"]["status"]}


# ------------------------------------------------------------------ simulation
def _insert_samples(conn, source, rows):
    for when, flux in rows:
        conn.execute("INSERT OR REPLACE INTO radiation_samples (source, time_tag, flux_pfu, satellite) VALUES (?, ?, ?, NULL)",
                     (source, when, flux))


# Three past events of the "history" scenario: (hours before now when it starts, duration in hours, peak pfu).
HISTORY_EVENTS = ((132.0, 6.0, 25.0), (76.0, 12.0, 250.0), (34.0, 5.0, 18.0))


def history_samples(now):
    """A week of 5 minute samples ending now: quiet, with three past solar events (S1, S2 and S1). SIMULATED demo data."""
    import random
    rng = random.Random(11)
    n = 7 * 24 * 12
    start = now.replace(second=0, microsecond=0) - timedelta(minutes=5 * (n - 1))
    rows = []
    for i in range(n):
        when = start + timedelta(minutes=5 * i)
        hours_ago = (now - when).total_seconds() / 3600
        quiet = 0.2 + rng.random() * 0.15
        flux = quiet
        for begins, length, peak in HISTORY_EVENTS:
            into = begins - hours_ago
            if 0 <= into <= length:
                rise = 0.3 * length
                share = into / rise if into < rise else 1 - (into - rise) / (length - rise)      # log-linear up, then down
                flux = max(flux, quiet * (peak / quiet) ** max(0.0, share))
        rows.append((_iso(when), round(flux, 3)))
    return rows


def scenario_samples(name, now):
    """Six hours of 5 minute samples ending now: quiet, then (for s1..s4) a storm that is at its peak right now."""
    import random
    if name == "history":
        return history_samples(now)
    rng = random.Random(7)
    peak = SCENARIO_PEAK_PFU.get(SCENARIOS[name])
    start = now.replace(second=0, microsecond=0) - timedelta(minutes=5 * 71)
    rows = []
    for i in range(72):
        when = start + timedelta(minutes=5 * i)
        quiet = 0.2 + rng.random() * 0.15
        flux = quiet
        if peak:
            onset, ramp = 24, 24                          # the storm begins two hours in and rises for two hours
            if i >= onset:
                rise = min(1.0, (i - onset) / ramp)       # log-linear rise: each decade takes about the same time
                flux = quiet * (peak / quiet) ** rise
                if i > onset + ramp:
                    flux *= 0.93 + 0.14 * rng.random()     # small wiggle at the peak
        if name == "prepare" and i >= 72 - 8:             # the particle level starts to rise in the last 40 minutes
            flux = 0.3 * (9.0 ** ((i - (72 - 8)) / 7))
        rows.append((_iso(when), round(flux, 3)))
    return rows


def sync_simulated_dose(conn, now=None):
    """Give each simulated event the illustrative dose of its highest S class (idempotent). Returns entries added."""
    result = evaluate(load_samples(conn, "simulated", 168, now), "simulated")
    added = 0
    for event in result["events"]:
        target = SIM_DOSE_MSV[event["s_class_peak"]] if event["s_class_peak"] else 0.0
        have = conn.execute("SELECT COALESCE(SUM(msv), 0) FROM radiation_dose WHERE source = 'simulated' AND event_ref = ?",
                            (event["id"],)).fetchone()[0]
        if target > have + 1e-9:
            at = max((a["at"] for a in result["alerts"] if a["event_id"] == event["id"]), default=event["started_at"])
            conn.execute("INSERT INTO radiation_dose (source, at, msv, origin, event_ref, note) VALUES "
                         "('simulated', ?, ?, 'simulated_event', ?, ?)",
                         (at, round(target - have, 4), event["id"],
                          f"Simulated S{event['s_class_peak']} event (illustrative demo dose, not from flux)"))
            added += 1
    return added


def simulate(conn, scenario, now=None):
    """Replace the simulated flux with a scenario (quiet, watch, prepare, s1 to s4, history). Simulated data only."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {sorted(SCENARIOS)}")
    now = _now(now)
    conn.execute("DELETE FROM radiation_samples WHERE source = 'simulated'")
    conn.execute("DELETE FROM radiation_dose WHERE source = 'simulated' AND origin = 'simulated_event'")
    conn.execute("DELETE FROM radiation_ack WHERE alert_id LIKE 'simulated:%'")
    rows = scenario_samples(scenario, now)
    _meta_set(conn, "simulated_scenario", scenario)
    _insert_samples(conn, "simulated", rows)
    sync_simulated_dose(conn, now)
    conn.commit()
    return {"scenario": scenario, "samples": len(rows)}


def add_simulated_sample(conn, flux, now=None):
    """Append one simulated flux sample at the current time (for stepping through a demonstration)."""
    if isinstance(flux, bool) or not isinstance(flux, (int, float)) or not math.isfinite(flux) or flux < 0:
        raise ValueError("flux must be a number of 0 or more (pfu)")
    now = _now(now)
    while conn.execute("SELECT 1 FROM radiation_samples WHERE source = 'simulated' AND time_tag = ?", (_iso(now),)).fetchone():
        now += timedelta(seconds=1)                        # two samples in the same second keep their own time
    _insert_samples(conn, "simulated", [(_iso(now), float(flux))])
    sync_simulated_dose(conn, now)
    conn.commit()
    return {"flux_pfu": float(flux), "time": _iso(now)}


# ------------------------------------------------------------------ the educational exposure budget
def get_config(conn, source, now=None):
    """The budget settings of one source. The baseline start time is set the first time they are read."""
    now = _now(now)
    config = {}
    for key, default in BUDGET_DEFAULTS.items():
        config[key] = float(_meta_get(conn, f"{source}:{key}", default))
    start = _meta_get(conn, f"{source}:baseline_start")
    if start is None:
        start = _iso(now)
        _meta_set(conn, f"{source}:baseline_start", start)
        conn.commit()
    config["baseline_start"] = start
    return config


def set_config(conn, source, changes, now=None):
    get_config(conn, source, now)
    for key, value in changes.items():
        if key not in BUDGET_LIMITS:
            raise ValueError(f"unknown setting '{key}'")
        low, high = BUDGET_LIMITS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key} must be a number between {low:g} and {high:g}")
        _meta_set(conn, f"{source}:{key}", float(value))
    conn.commit()
    return get_config(conn, source, now)


def add_operator_dose(conn, source, msv, note, now=None):
    if isinstance(msv, bool) or not isinstance(msv, (int, float)) or not math.isfinite(msv) or not 0 < msv <= 1000:
        raise ValueError("msv must be a number above 0 and at most 1000")
    if note is not None and (not isinstance(note, str) or len(note) > 200):
        raise ValueError("note must be text of at most 200 characters")
    conn.execute("INSERT INTO radiation_dose (source, at, msv, origin, event_ref, note) VALUES (?, ?, ?, 'operator_entered', NULL, ?)",
                 (source, _iso(_now(now)), float(msv), (note or "").strip() or "Entered by the operator"))
    conn.commit()


def _day_factor(source, day):
    """Simulated day-to-day variation of the background (cosmic ray flux, shielding, activity): the same value for a given day."""
    import random
    return random.Random(f"{source}:{day}").uniform(1 - DAILY_VARIATION, 1 + DAILY_VARIATION)


def _days(rate, remaining):
    if remaining <= 0:
        return 0.0
    return None if rate <= 0 else remaining / rate


def budget(conn, source, now=None):
    """D_remaining = D_budget - D_accumulated and T = D_remaining / R_projected, with every assumption named."""
    now = _now(now)
    config = get_config(conn, source, now)
    rate, start = config["baseline_rate_msv_day"], _utc(config["baseline_start"])

    def accrued(moment):
        return rate * max(0.0, (moment - start).total_seconds() / 86400)

    entries = [dict(r) for r in conn.execute("SELECT at, msv, origin, event_ref, note FROM radiation_dose "
                                             "WHERE source = ? ORDER BY at, id", (source,))]
    running, rows = 0.0, []
    for entry in entries:
        moment = _utc(entry["at"])
        before = config["initial_msv"] + accrued(moment) + running
        running += entry["msv"]
        after = before + entry["msv"]
        rem_b, rem_a = config["budget_msv"] - before, config["budget_msv"] - after
        d_b, d_a = _days(rate, rem_b), _days(rate, rem_a)
        rows.append({**entry, "label": "simulated" if entry["origin"] == "simulated_event" else "self_reported",
                     "remaining_before_msv": round(rem_b, 2), "remaining_after_msv": round(rem_a, 2),
                     "days_before": None if d_b is None else round(d_b, 1), "days_after": None if d_a is None else round(d_a, 1)})
    accumulated = config["initial_msv"] + accrued(now) + running
    remaining = config["budget_msv"] - accumulated
    days = _days(rate, remaining)
    day_ago = now - timedelta(hours=24)
    last_24h = sum(e["msv"] for e in entries if _utc(e["at"]) >= day_ago)
    daily = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        events_msv = sum(e["msv"] for e in entries if e["at"][:10] == day)
        background = rate * _day_factor(source, day)
        daily.append({"date": day, "background_msv": round(background, 3), "event_msv": round(events_msv, 3),
                      "total_msv": round(background + events_msv, 3)})
    today_background = rate * _day_factor(source, now.strftime("%Y-%m-%d"))
    elapsed = int((now - start).total_seconds() // 86400)
    day_now = int(config["mission_day"]) + elapsed
    days_total = int(config["mission_days"])
    days_left = max(0, days_total - day_now)
    projected = accumulated + days_left * rate
    mission = {"assumed": True, "days_total": days_total, "day_now": day_now, "days_left": days_left,
               "projected_total_msv": round(projected, 1), "limit_msv": config["budget_msv"],
               "within_limit": projected < config["budget_msv"],
               "note": "A demo mission chosen for now. Days left use the assumed background rate; real rates and solar events change the result."}
    last = rows[-1] if rows else None
    why = None
    if last:
        why = (f"{last['note']}: +{last['msv']:g} mSv. Remaining budget {last['remaining_before_msv']:g} -> "
               f"{last['remaining_after_msv']:g} mSv"
               + (f"; estimated remaining days {last['days_before']:g} -> {last['days_after']:g} at {rate:g} mSv/day."
                  if last["days_before"] is not None and last["days_after"] is not None else "."))
    return {
        "source": source, "label": "simulated" if source == "simulated" else "self_reported",
        "kind": "estimate", "budget_msv": config["budget_msv"], "initial_msv": config["initial_msv"],
        "baseline_rate_msv_day": rate, "baseline_start": config["baseline_start"],
        "baseline_accrued_msv": round(accrued(now), 3), "event_dose_msv": round(running, 3),
        "accumulated_msv": round(accumulated, 2), "remaining_msv": round(max(0.0, remaining), 2),
        "used_share": round(min(1.0, max(0.0, accumulated / config["budget_msv"])), 3),
        "exceeded": remaining < 0, "estimated_days_remaining": None if days is None else round(days, 1),
        "daily_background_msv": round(today_background, 3), "daily_event_msv_24h": round(last_24h, 3),
        "daily_exposure_msv": round(today_background + last_24h, 3), "daily": daily, "mission": mission,
        "limit_name": "NASA career effective dose limit (NASA-STD-3001 Vol 1, V1 4030)",
        "formula": "D_remaining = D_budget - D_accumulated; T = D_remaining / R_projected",
        "why_it_changed": why, "entries": list(reversed(rows)),
        "dose_status": ("Event doses are not estimated from NOAA flux. Enter a dose yourself (for example from a dosimeter "
                        "reading) to update the budget." if source == "external" else
                        "Simulated events add the illustrative demonstration doses listed in the entries."),
        "assumptions": [
            "The mission (length and current day) and the dose received so far are demo assumptions the user can change. The daily background varies by up to 35% around the average rate as a simulated variation; the total uses the average rate.",
            "The limit is NASA's career effective dose limit of 600 mSv (NASA-STD-3001 Vol 1 [V1 4030], universal for all ages and sexes). The dose already received is entered by the user.",
            f"R_projected is the assumed background dose rate ({rate:g} mSv/day) staying constant; real rates change with "
            "location, shielding, activity and the solar cycle.",
            "Dose is never computed from proton flux. A valid conversion needs radiation transport and a shielding model.",
            "The result is not a medically certified safe mission duration."],
        "disclaimer": DISCLAIMER,
    }

"""Radiation outlook: a staged heads-up (clear, watch, prepare, build, shelter) and what to do at each stage.

ASTRA cannot predict a solar storm. NASA says solar particle storms are hard to predict and that the forecast models are
still in an early stage. What ASTRA can do is show the early signs that NOAA publishes, and the particle level itself:
  watch    a strong flare (M or X class), a solar radio burst, or NOAA's own chance of a radiation storm is high
  prepare  the particle level is rising, a very strong flare (X class) happened, or the S1 level is reached
  build    the storm is at S2 or S3 (ASTRA alert level 2): build the shelter now
  shelter  the storm is at S4 or S5 (ASTRA alert level 3): stay in the shelter
Thresholds are ASTRA's own choices (documented in docs/RADIATION_MONITOR.md), not NASA rules. Dose is never computed.
The shelter idea (a temporary shelter made of stowage bags, food and water) is NASA's plan for the Orion capsule.
"""
import json
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import radiation

SWPC = "https://services.swpc.noaa.gov/"
FILES = {"xray": "json/goes/primary/xrays-6-hour.json", "scales": "products/noaa-scales.json",
         "alerts": "products/alerts.json"}
TTL_S = 300                    # the early-warning files are fetched at most every 5 minutes
M_FLARE, X_FLARE = 1e-5, 1e-4  # GOES 0.1-0.8 nm flux (W/m2): M class and X class
FLARE_WINDOW_H = 6             # a flare or radio burst counts as a sign for this long
X_FLARE_WINDOW_H = 3
PROB_WATCH = 20                # NOAA's chance (%) of a radiation storm today at which we say "watch" (ASTRA's choice)
RISING_MIN_PFU = 1.0           # the level must be at least this to count as "rising"
RISING_FACTOR = 1.5            # and at least this many times what it was 30 minutes ago
RISING_LOOKBACK_MIN = 30

STAGES = [("clear", "All clear"), ("watch", "Watch"), ("prepare", "Prepare"), ("build", "Build the shelter"),
          ("shelter", "Shelter")]
NASA, ASTRA = "nasa", "astra"

SOURCES_LIST = [
    {"label": "NASA: How NASA will protect astronauts from space radiation at the Moon (Orion shelter, forecasting)",
     "url": "https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon"},
    {"label": "NOAA SWPC: radiation storm scale and three-day forecast (noaa-scales.json)", "url": SWPC + "products/noaa-scales.json"},
    {"label": "NOAA SWPC: alerts, watches and warnings (alerts.json)", "url": SWPC + "products/alerts.json"},
]

TEXT = {
    "clear": ("No sign of a solar storm right now.", [
        ("Nothing to do now. It is still a good idea to know where your shelter area is and what you would build it from.", ASTRA)]),
    "watch": ("The Sun is active. A radiation storm is possible in the next hours, but it is not certain.", [
        ("Do not start a long job outside the spacecraft if it can wait. NASA's radiation group can advise postponing outside work when particle levels rise.", NASA),
        ("Find your shelter area and think about how you would get there.", ASTRA),
        ("Look at this page again in 30 minutes and listen to mission control.", ASTRA)]),
    "prepare": ("Particle levels are rising or a very strong flare happened. A storm may be starting.", [
        ("Finish or stop outside work and come inside.", ASTRA),
        ("Gather the dense things you would build with: bags of water, food and supplies. NASA's plan for the Orion capsule builds the shelter from stowage bags, food and water already on board.", NASA),
        ("Put them close to your shelter area so you can move them fast.", ASTRA),
        ("Wear your radiation badge (dosimeter) if you have one.", ASTRA),
        ("Tell mission control and a crew mate what you see.", ASTRA)]),
    "build": ("Build your shelter now. The storm is strong (S2 or S3).", [
        ("Put the densest items, water and food first, against the thinnest walls of your shelter area.", NASA),
        ("Start early: news reports on Orion's plan say building takes about 30 to 60 minutes.", ASTRA),
        ("Stay inside the spacecraft. No outside work.", NASA),
        ("Follow mission control. They decide how long you stay.", ASTRA)]),
    "shelter": ("Go to your shelter now. The storm is very strong (S4 or S5).", [
        ("Go to your shelter area and stay there until mission control says the storm is over.", ASTRA),
        ("Keep the dense supplies around you. Do not go outside.", ASTRA),
        ("Tell mission control that you are in the shelter and how you feel.", ASTRA),
        ("Wait for the all-clear from mission control and NASA's radiation group. ASTRA does not give it.", NASA)]),
    "unknown": ("There is no current radiation data, so ASTRA cannot say what is happening.", [
        ("Do not assume everything is fine. Check the connection and listen to mission control.", ASTRA)]),
}

LIMITS = ("ASTRA cannot predict a solar storm. NASA says these storms are hard to predict and that the forecast models are "
          "still early. ASTRA shows three early signs from NOAA (strong flares, solar radio bursts and NOAA's own chance of a "
          "storm) and the particle level itself. Some storms start with almost no warning, and many flares are followed by "
          "nothing. In a real mission, mission control and NASA's radiation group decide what to do.")


# ------------------------------------------------------------------ early signs from NOAA
def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ASTRA-educational-prototype"})
    with urllib.request.urlopen(request, timeout=radiation.FETCH_TIMEOUT_S) as answer:
        return json.loads(answer.read().decode("utf-8"))


def flare_class(flux):
    """GOES flare class text from the 0.1-0.8 nm flux, for example 5.2e-5 -> 'M5.2'."""
    for letter, base in (("X", 1e-4), ("M", 1e-5), ("C", 1e-6), ("B", 1e-7), ("A", 1e-8)):
        if flux >= base:
            return f"{letter}{flux / base:.1f}"
    return "A0.0"


def parse_flare(records, now):
    """The strongest flare of the last FLARE_WINDOW_H hours from the GOES X-ray records, or None."""
    best = None
    since = now - timedelta(hours=FLARE_WINDOW_H)
    for r in records if isinstance(records, list) else []:
        try:
            if r.get("energy") != "0.1-0.8nm":
                continue
            flux = r["flux"]
            when = radiation._utc(r["time_tag"])
            if isinstance(flux, bool) or not isinstance(flux, (int, float)) or flux <= 0 or when < since or when > now:
                continue
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if best is None or flux > best["flux"]:
            best = {"flux": float(flux), "class": flare_class(flux), "at": radiation._iso(when)}
    return best


def parse_alerts(records, now):
    """(radio burst, proton warning) from NOAA's alert list, each a dict {text, at} or None, within the last hours."""
    radio = warning = None
    for r in records if isinstance(records, list) else []:
        try:
            message = r["message"]
            issued = datetime.strptime(r["issue_datetime"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, TypeError, ValueError):
            continue
        age = (now - issued).total_seconds() / 3600
        if age < 0 or age > FLARE_WINDOW_H * 2:
            continue
        if "Type II Radio Emission" in message or "Type IV Radio Emission" in message:
            kind = "II" if "Type II" in message else "IV"
            if age <= FLARE_WINDOW_H and (radio is None or issued > _utc_of(radio)):
                radio = {"type": kind, "at": radiation._iso(issued)}
        if "Proton" in message and ("WARNING" in message or "WATCH" in message):
            if warning is None or issued > _utc_of(warning):
                warning = {"text": "NOAA issued a proton warning or watch", "at": radiation._iso(issued)}
    return radio, warning


def _utc_of(item):
    return radiation._utc(item["at"])


def parse_probability(data):
    """NOAA's chance (%) of a radiation storm (S1 or more) today, from noaa-scales.json, or None."""
    try:
        value = data["1"]["S"]["Prob"]
        return int(value) if value not in (None, "") else None
    except (KeyError, TypeError, ValueError):
        return None


def fetch_extras(fetch=None, now=None):
    """Download the early signs. Never raises: a missing file only means that sign is unavailable."""
    now = radiation._now(now)
    fetch = fetch or _fetch
    out = {"available": False, "errors": [], "flare": None, "radio": None, "proton_warning": None,
           "prob_s1": None, "fetched_at": radiation._iso(now)}
    ok = 0
    for key, parse in (("xray", lambda d: out.update(flare=parse_flare(d, now))),
                       ("alerts", lambda d: out.update(zip(("radio", "proton_warning"), parse_alerts(d, now)))),
                       ("scales", lambda d: out.update(prob_s1=parse_probability(d)))):
        try:
            parse(fetch(SWPC + FILES[key]))
            ok += 1
        except Exception as error:                      # network down, bad JSON, timeout
            out["errors"].append(f"{key}: {type(error).__name__}")
    out["available"] = ok > 0
    return out


_cache = {"at": 0.0, "value": None}
_lock = threading.Lock()


def get_extras(fetch=None, now=None):
    """The early signs, fetched at most every TTL_S seconds. A failed refresh keeps the last good answer."""
    with _lock:
        if _cache["value"] is None or time.time() - _cache["at"] >= TTL_S:
            fresh = fetch_extras(fetch, now)
            if fresh["available"] or _cache["value"] is None:
                _cache["value"] = fresh
            _cache["at"] = time.time()
        return _cache["value"]


def peek_extras():
    """The last downloaded early signs, never fetching (for notifications). None if nothing was fetched yet."""
    return _cache["value"]


def reset_cache():
    with _lock:
        _cache["at"], _cache["value"] = 0.0, None


def simulated_extras(scenario, now):
    """Made-up early signs for the demo scenarios (the Radiation page demo menu)."""
    now = radiation._now(now)
    if scenario == "watch":
        return {"available": True, "errors": [], "flare": {"flux": 5.2e-5, "class": "M5.2", "at": radiation._iso(now - timedelta(minutes=50))},
                "radio": {"type": "II", "at": radiation._iso(now - timedelta(minutes=42))}, "proton_warning": None, "prob_s1": 30,
                "fetched_at": radiation._iso(now)}
    if scenario in ("prepare", "s1", "s2", "s3", "s4"):
        return {"available": True, "errors": [], "flare": {"flux": 1.3e-4, "class": "X1.3", "at": radiation._iso(now - timedelta(minutes=95))},
                "radio": {"type": "II", "at": radiation._iso(now - timedelta(minutes=88))}, "proton_warning": None, "prob_s1": 60,
                "fetched_at": radiation._iso(now)}
    return {"available": True, "errors": [], "flare": None, "radio": None, "proton_warning": None, "prob_s1": 5,
            "fetched_at": radiation._iso(now)}


# ------------------------------------------------------------------ the stage
def rising(samples):
    """(is rising, now, before): the level is at least RISING_MIN_PFU and RISING_FACTOR times what it was 30 minutes ago."""
    if len(samples) < 2:
        return False, None, None
    when_now, now_flux = samples[-1]
    target = radiation._utc(when_now) - timedelta(minutes=RISING_LOOKBACK_MIN)
    before = None
    for when, flux in samples:
        if radiation._utc(when) <= target:
            before = flux
    if before is None or before <= 0:
        return False, now_flux, before
    return now_flux >= RISING_MIN_PFU and now_flux >= RISING_FACTOR * before, now_flux, before


def _hhmm(iso):
    return iso[11:16] + " UTC"


def outlook(conn, source, extras=None, now=None):
    now = radiation._now(now)
    st = radiation.status(conn, source, now)
    state = st["state"]
    level = state["level"]
    samples = radiation.load_samples(conn, source, 2, now)
    is_rising, flux_now, flux_before = rising(samples)
    if source == "simulated":
        extras = simulated_extras(radiation._meta_get(conn, "simulated_scenario", "quiet"), now)
    extras = extras or {"available": False, "errors": [], "flare": None, "radio": None, "proton_warning": None, "prob_s1": None}
    flare = extras.get("flare")
    big_flare = bool(flare and flare["flux"] >= M_FLARE)
    x_flare = bool(flare and flare["flux"] >= X_FLARE and (now - radiation._utc(flare["at"])).total_seconds() <= X_FLARE_WINDOW_H * 3600)
    radio = extras.get("radio")
    prob = extras.get("prob_s1")
    warn = extras.get("proton_warning")

    if st["data_status"] in ("no_data", "stale"):
        key = "unknown"
    elif level >= 3:
        key = "shelter"
    elif level == 2:
        key = "build"
    elif level == 1 or is_rising or x_flare or warn:
        key = "prepare"
    elif big_flare or radio or (prob is not None and prob >= PROB_WATCH):
        key = "watch"
    else:
        key = "clear"

    signals = []
    if extras["available"] or source == "simulated":
        signals.append({"key": "flare", "active": big_flare,
                        "text": (f"Solar flare {flare['class']} at {_hhmm(flare['at'])}. M and X class flares are the strong ones."
                                 if big_flare else "No strong solar flare (M or X class) in the last 6 hours.")})
        signals.append({"key": "radio", "active": bool(radio),
                        "text": (f"NOAA reported a solar radio burst (type {radio['type']}) at {_hhmm(radio['at'])}. It can be a sign of a particle cloud leaving the Sun."
                                 if radio else "No solar radio burst reported in the last 6 hours.")})
        if warn:
            signals.append({"key": "warning", "active": True, "text": f"{warn['text']} at {_hhmm(warn['at'])}."})
        signals.append({"key": "forecast", "active": prob is not None and prob >= PROB_WATCH,
                        "text": ("NOAA's forecast is not available." if prob is None
                                 else f"NOAA gives a {prob}% chance of a radiation storm (S1 or more) today.")})
    else:
        signals.append({"key": "early", "active": False, "text": "The early signs from NOAA are not available right now."})
    signals.append({"key": "rising", "active": is_rising,
                    "text": (f"The particle level is rising: {radiation._flux_text(flux_before)} to {radiation._flux_text(flux_now)} in 30 minutes."
                             if is_rising else "The particle level is not rising fast.")})
    headline, steps = TEXT[key]
    index = next((i for i, (k, _) in enumerate(STAGES) if k == key), None)
    return {"source": source, "generated_at": radiation._iso(now),
            "stage": {"key": key, "index": index, "title": dict(STAGES).get(key, "No data"), "headline": headline,
                      "steps": [{"text": t, "tag": tag} for t, tag in steps]},
            "stages": [{"key": k, "title": t} for k, t in STAGES], "signals": signals,
            "early_signs_available": bool(extras["available"]), "limits": LIMITS, "sources": SOURCES_LIST,
            "disclaimer": radiation.DISCLAIMER}


def notice_item(conn, now=None):
    """A notification for the Overview when the stage is watch or prepare. Uses the last downloaded early signs only."""
    best = None
    for source in radiation.SOURCES:
        result = outlook(conn, source, peek_extras() if source == "external" else None, now)
        key = result["stage"]["key"]
        if key in ("watch", "prepare") and (best is None or result["stage"]["index"] > best[1]["stage"]["index"]):
            best = (source, result)
    if best is None:
        return None
    source, result = best
    stage = result["stage"]
    title = "Radiation watch: the Sun is active" if stage["key"] == "watch" else "Get ready: radiation levels may rise"
    return {"id": "radiation_outlook", "level": "warning", "title": title,
            "message": stage["headline"] + (" (simulated)" if source == "simulated" else ""),
            "page": "radiation.html", "target": "outlook-h",
            "advice": {"meaning": stage["headline"] + " " + LIMITS, "steps": [s["text"] for s in stage["steps"]]}}

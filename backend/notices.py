"""Notifications (traffic light), daily suggestions and the advice behind them (contract section 6.14). Read only.

Every notification comes from a documented rule applied to the person's own data of ONE source. The
colors mean what the user should do, not a medical judgement:
  ok       nothing to do
  warning  look at it when you can
  danger   needs action now (the data stopped, or a value is far outside the person's own usual range)
Each item says which page to open (`page`, `target`) and carries the advice shown there. ASTRA is an
educational prototype: the advice never diagnoses and never replaces medical help.
"""
import math
from datetime import datetime

import analysis
import outlook
import radiation
import rest

STALE_S = 10            # seconds without a new reading before "warning" (five readings at 2 s)
LOST_S = 300            # seconds without a new reading before "danger"
HR_DANGER_FACTOR = 2.0  # danger when the heart rate difference is more than this x the observation limit
SIGNAL_MIN_GOOD = 0.7   # share of today's readings with a good signal below which we warn
SIGNAL_MIN_READINGS = 10
INACTIVE_MIN = 60        # minutes without movement while awake before the warning (ASTRA's own choice)
BLOCK_MIN = 5
STILL_G = 0.05          # same stillness limit as the rest analysis (rest.py)
AWAKE_FROM_H, AWAKE_TO_H = 7, 22   # the hours in which stillness counts (ASTRA's own assumption)
DISCLAIMER = analysis.DISCLAIMER

LEVEL_ORDER = {"danger": 0, "warning": 1, "ok": 2}


def _item(item_id, level, title, message, page, target, meaning, steps):
    return {"id": item_id, "level": level, "title": title, "message": message, "page": page, "target": target,
            "advice": {"meaning": meaning, "steps": steps}}


def _where(source):
    return ("Check that python simulator.py is running in backend/ and that the server is running."
            if source == "simulated" else
            "Check that the ESP32 has power and is connected to the same 2.4 GHz Wi-Fi as the laptop "
            "(or that python simulator.py is running)."
            if source == analysis.DASHBOARD else
            "Check that the ESP32 has power and is connected to the same 2.4 GHz Wi-Fi as the laptop.")


def _connection(conn, source, now):
    where, params = analysis.source_where(conn, source)
    row = conn.execute(f"SELECT received_at FROM measurements WHERE {where} ORDER BY received_at DESC, id DESC "
                       "LIMIT 1", params).fetchone()
    if row is None:
        return _item("connection", "warning", "Waiting for the first reading",
                     "No readings have arrived yet.", "sensors.html", "alert-h",
                     "ASTRA has not received anything from the sensor yet, so there is nothing to show.",
                     [_where(source), "Open the Sensors page to see when the first reading arrives.",
                      "Start the sensor, or the simulator, so that today has readings."])
    seconds = max(0.0, (now - datetime.fromisoformat(row["received_at"])).total_seconds())
    if seconds > LOST_S:
        return _item("connection", "danger", "Data stopped",
                     f"No new readings for {round(seconds / 60)} min.", "sensors.html", "alert-h",
                     "The sensor or the laptop stopped sending data. What you see on the screen is old. It is not "
                     "how you are right now.",
                     [_where(source), "Check that the laptop is on the same Wi-Fi and that the ASTRA program is still running.",
                      "When readings come back, this message turns green by itself.",
                      "If you feel unwell, do not wait for the screen: tell your crew medical officer or a crew mate."])
    if seconds > STALE_S:
        return _item("connection", "warning", "No new readings",
                     f"Last reading {round(seconds)} s ago.", "sensors.html", "alert-h",
                     "New readings are late. The numbers on the screen are the last ones that arrived.",
                     [_where(source), "Wait a few seconds. A slow Wi-Fi connection can cause a short gap.",
                      "If it lasts, open the Sensors page and check the signal."])
    return _item("connection", "ok", "Device is sending", "New readings are arriving.", "sensors.html", "alert-h",
                 "Readings are arriving normally.", [])


def _heart_rate(obs):
    b = obs["based_on"]
    diff, limit = b["difference"], b["limit"]
    word = "higher" if diff > 0 else "lower"
    if obs["level"] != "notable":
        return _item("hr_vs_baseline", "ok", "Heart rate is as usual",
                     f"Today's average {b['today_median']} bpm, usual {b['baseline_median']} bpm.",
                     "timeline.html", "hr-h", "Your heart rate today is close to your usual.", [])
    level = "danger" if abs(diff) > HR_DANGER_FACTOR * limit else "warning"
    steps = ["Sit down, drink a glass of water and rest quietly for 10 minutes.",
             "Then measure again: finger flat on the sensor, hand still, wait for a steady signal. Measure once more an hour later.",
             "For the next hour, avoid coffee, hard exercise and stressful tasks."]
    if level == "danger":
        steps.append("Emergency signs (chest pain or pressure, dizziness, fainting, a pounding or uneven heartbeat, trouble "
                     "breathing): call your crew for help now, follow your onboard emergency procedures and contact mission "
                     "control at the same time. Do not wait for their reply. If the number only stays high after resting, tell "
                     "your crew medical officer. ASTRA cannot judge your health.")
    return _item("hr_vs_baseline", level, f"Heart rate {word} than usual",
                 f"Today's average {b['today_median']} bpm, usual {b['baseline_median']} bpm "
                 f"({'+' if diff > 0 else ''}{diff} bpm, normal change ±{limit}).", "timeline.html", "hr-h",
                 f"Your average heart rate today is {abs(diff)} beats per minute {word} than your usual "
                 f"({b['baseline_median']}). That is more than your normal day-to-day change (±{limit}). Heart rate also "
                 "changes with exercise, stress, coffee, sleep and how well the sensor reads. This is a notice from a "
                 "rule, not a diagnosis.", steps)


def _spo2(obs):
    b = obs["based_on"]
    diff, limit = b["difference"], b["limit"]
    word = "higher" if diff > 0 else "lower"
    if obs["level"] != "notable":
        return _item("spo2_vs_baseline", "ok", "Blood oxygen is as usual",
                     f"Today's average {b['today_median']}%, usual {b['baseline_median']}%.", "timeline.html", "hr-h",
                     "Your blood oxygen estimate today is close to your usual.", [])
    steps = ["Sit upright, breathe slowly and deeply, and warm your hand. Cold fingers give low numbers.",
             "After 5 minutes, put your finger flat on the sensor and measure once more.",
             "If the signal is poor, ignore the number. The Sensors page shows the signal."]
    if diff < 0:
        steps.append("Emergency signs (short of breath, dizzy, confused): call your crew for help now and contact mission "
                     "control at the same time. If the number only stays low after resting, tell your crew medical officer. "
                     "This sensor is an experimental estimate, not a medical device.")
    return _item("spo2_vs_baseline", "warning", f"Blood oxygen {word} than usual",
                 f"Today's average {b['today_median']}%, usual {b['baseline_median']}% ({'+' if diff > 0 else ''}{diff} points).",
                 "timeline.html", "hr-h",
                 f"Your blood oxygen estimate (SpO2) today is {abs(diff)} points {word} than your usual "
                 f"({b['baseline_median']}%). A finger sensor can read low when the hand is cold, moving or badly placed, "
                 "so this is only a notice to measure again.", steps)


def _rest(obs):
    b = obs["based_on"]
    if obs["level"] != "notable":
        return _item("rest_start_vs_usual", "ok", "Rest started as usual",
                     f"Last night's rest started {b['last_night']}, usual {b['usual']}.", "activity.html", "rest-h",
                     "Last night you went to rest at about your usual time.", [])
    return _item("rest_start_vs_usual", "warning", "Rest started at an unusual time", obs["message"],
                 "activity.html", "rest-h",
                 f"Last night's rest started at {b['last_night']}. You usually start around {b['usual']}. ASTRA works "
                 "this out from movement only, and one night is not a pattern.",
                 [f"Go to rest around {b['usual']} tonight and get up at your usual time.",
                  "Dim bright lights in the hour before rest.",
                  "Keep the sleeping area dark, quiet and cool, and avoid hard exercise right before rest."])


def _rest_length(obs):
    b = obs["based_on"]
    if obs["level"] != "notable":
        return _item("rest_length_vs_usual", "ok", "Rest length is as usual",
                     f"Last night's rest was {b['last_night_h']} h, usual {b['usual_h']} h.", "activity.html", "rest-h",
                     "Last night's rest was about as long as usual.", [])
    word = "longer" if b["difference_min"] > 0 else "shorter"
    steps = (["Go to rest at your usual time tonight and keep your usual wake-up time.",
              "Dim the lights in the hour before rest. Keep the sleeping area dark, quiet and cool.",
              "Avoid hard exercise right before rest. Exercise earlier in the day instead.",
              "If you feel very sleepy, tell a crew mate before you start a task that needs your full attention."]
             if word == "shorter" else
             ["Keep your usual rest and wake-up times tonight.",
              "If you feel unusually tired, drink water, eat something and take a short walk."])
    return _item("rest_length_vs_usual", "warning", f"Rest was {word} than usual", obs["message"],
                 "activity.html", "rest-h",
                 f"ASTRA estimates rest from movement. Last night's rest was {b['last_night_h']} h and you usually rest "
                 f"about {b['usual_h']} h. This is an estimate, not a sleep measurement. One {word} night is common; "
                 "several in a row are worth acting on.", steps)


def _inactivity(conn, source, date, now):
    """No movement for an hour or more while awake (ASTRA's own rule, 7:00 to 22:00), from the ICM-20948."""
    if date != analysis.today_local():
        return None
    local = now.astimezone()
    if not (AWAKE_FROM_H <= local.hour < AWAKE_TO_H):
        return None
    blocks = {}
    for r in analysis._rows(conn, source, date, date):
        ax, ay, az = r["accel_x_g"], r["accel_y_g"], r["accel_z_g"]
        if None in (ax, ay, az):
            continue
        minute = int(r["received_at"][11:13]) * 60 + int(r["received_at"][14:16])
        blocks.setdefault(minute // BLOCK_MIN, []).append(abs(math.sqrt(ax * ax + ay * ay + az * az) - 1.0))
    now_block = (local.hour * 60 + local.minute) // BLOCK_MIN
    newest = next((k for k in (now_block, now_block - 1) if k in blocks), None)
    if newest is None or len(blocks) * BLOCK_MIN < 30:
        return None                                   # no current motion data: the connection notice covers it
    first_awake = AWAKE_FROM_H * 60 // BLOCK_MIN
    run, k = 0, newest
    while k >= first_awake and k in blocks and sum(blocks[k]) / len(blocks[k]) < STILL_G:
        run += 1
        k -= 1
    minutes = run * BLOCK_MIN
    if minutes < INACTIVE_MIN:
        return _item("inactivity", "ok", "Movement is normal",
                     "You have moved within the last hour." if minutes < 30 else f"Still for {minutes} min so far.",
                     "activity.html", "today-h", "You have not been still for a long time today.", [])
    hours = f"{minutes // 60} h {minutes % 60} min" if minutes % 60 else f"{minutes // 60} h"
    return _item("inactivity", "warning", f"No movement for {hours}",
                 f"The sensor has seen almost no movement for {hours} while you should be awake.", "activity.html", "today-h",
                 "Sitting or lying still for a long time is not good for the body. It can also mean the device is lying "
                 "on a table and not on you.",
                 ["Stand up. Walk around or stretch for 3 to 5 minutes.",
                  "Check that you are wearing the device. If it is on a table, put it back on.",
                  "During long tasks, stand up for a minute about once an hour.",
                  "If you cannot move because you feel unwell, tell your crew medical officer or a crew mate."])


def _signal(conn, source, date):
    day = analysis.quality(conn, source, date, 1)["per_day"][-1]
    if day["total"] < SIGNAL_MIN_READINGS:
        return None
    share = day["good"] / day["total"]
    if share >= SIGNAL_MIN_GOOD:
        return _item("signal_quality", "ok", "Signal quality is good", f"{round(share * 100)}% of today's readings.",
                     "sensors.html", "alert-h", "Most of today's readings are clean.", [])
    return _item("signal_quality", "warning", "Signal quality is low",
                 f"Only {round(share * 100)}% of today's readings are clean.", "sensors.html", "alert-h",
                 "Bad readings are not used for your usual values or for the notices, so ASTRA can say less when the "
                 "signal is poor.",
                 ["Clean and dry your finger and the sensor window.",
                  "Put the finger on the sensor with light, steady pressure: not too tight, not loose.",
                  "Keep your hand still, at the height of your heart, away from strong light.",
                  "Check the Sensors page again in a few minutes."])


def _wear(conn, source, date):
    day = rest.wear(conn, source, date, 1)["per_day"][-1]
    if not day["readings"]:
        return None
    if day["enough"]:
        return _item("wear_time", "ok", "Wear time is enough", f"{round(day['coverage'] * 100)}% of the day has data.",
                     "sensors.html", "alert-h", "Data covers most of the day.", [])
    return _item("wear_time", "warning", "Data has gaps today",
                 f"{round(day['coverage'] * 100)}% of the day has data, longest gap {day['longest_gap_h']} h.",
                 "sensors.html", "alert-h",
                 "Your rest and your usual values are less reliable when the device is worn only part of the time.",
                 ["Put the device back on and keep it on for the rest of the day, including the night.",
                  "If you took it off on purpose, nothing else needs to be done."])


def _suggestions(conn, source, date, notes, base_ready, rest_ok):
    out = []
    j_where, j_params = analysis.journal_where(source)
    has_checkin = conn.execute(f"SELECT 1 FROM journal WHERE {j_where} AND date = ?", (*j_params, date)).fetchone()
    if not has_checkin:
        out.append({"id": "s_checkin", "title": "Fill in today's check-in", "page": "journal.html", "target": "form-h",
                    "text": "Two minutes: mood, energy, stress and tiredness.",
                    "advice": {"meaning": "The check-in is what you tell ASTRA yourself. It explains what the sensors show "
                               "and is never mixed with sensor data.",
                               "steps": ["Pick 1 to 5 for mood, energy, stress and tiredness. You can skip any question.",
                                         "Add a note if something was different today.",
                                         "Press Save check-in."]}})
    if any(n["level"] != "ok" and n["id"] in ("hr_vs_baseline", "spo2_vs_baseline", "rest_start_vs_usual",
                                              "rest_length_vs_usual", "inactivity") for n in notes):
        out.append({"id": "s_note", "title": "Add a note about what changed today", "page": "journal.html",
                    "target": "j-note", "text": "A note helps you understand the notifications later.",
                    "advice": {"meaning": "A notification only says that something differs from your usual. Your own note "
                               "explains why.",
                               "steps": ["Open the check-in and write one or two sentences in the note "
                                         "(exercise, coffee, stress, a late night).", "Press Save check-in."]}})
    if rest_ok:
        out.append({"id": "s_rest", "title": "Look at last night's rest", "page": "activity.html", "target": "rest-h",
                    "text": "See when your rest started and ended.",
                    "advice": {"meaning": "ASTRA estimates your rest from movement. Comparing nights shows how regular you are.",
                               "steps": ["Read the summary: start, end, wake-ups and resting heart rate.",
                                         "Compare last night with the other nights in the chart.",
                                         "Write in the check-in anything that explains a different night."]}})
    else:
        out.append({"id": "s_rest_data", "title": "Wear the sensor tonight", "page": "activity.html", "target": "rest-h",
                    "text": "ASTRA needs movement data from the night to show your rest.",
                    "advice": {"meaning": "There is not enough movement data from the night to find your rest.",
                               "steps": ["Wear the device through the night and keep it connected.",
                                         "Check on the Sensors page that readings keep arriving.",
                                         "Look at the rest chart on the Activity page tomorrow."]}})
    if not base_ready:
        out.append({"id": "s_baseline", "title": "Collect days for your usual values", "page": "timeline.html",
                    "target": "hr-h", "text": "ASTRA needs 3 days with enough good readings.",
                    "advice": {"meaning": "Your usual values are what ASTRA compares today with. Until they exist, it cannot "
                               "say whether today is different.",
                               "steps": ["Wear the device for most of the day.", "Keep your finger in the same place so the "
                                         "signal stays good.", "Open the Timeline to see how many days are counted."]}})
    out.append({"id": "s_timeline", "title": "Compare today with the last days", "page": "timeline.html", "target": "hr-h",
                "text": "Heart rate, movement and your check-in side by side.",
                "advice": {"meaning": "Looking at the days together shows patterns that one number hides.",
                           "steps": ["Select today and the days before it.",
                                     "Look at whether heart rate and movement went up and down together.",
                                     "Compare with how you rated your energy and tiredness."]}})
    return out


def compute(conn, source, date, now=None):
    now = now or datetime.now().astimezone()
    notes = []
    if date == analysis.today_local():
        notes.append(_connection(conn, source, now))
    obs = analysis.observation(conn, source, date)
    by_id = {o["id"]: o for o in obs["observations"]}
    base_ready = "hr_vs_baseline" in by_id
    if "hr_vs_baseline" in by_id:
        notes.append(_heart_rate(by_id["hr_vs_baseline"]))
    if "rest_start_vs_usual" in by_id:
        notes.append(_rest(by_id["rest_start_vs_usual"]))
    if "rest_length_vs_usual" in by_id:
        notes.append(_rest_length(by_id["rest_length_vs_usual"]))
    if "spo2_vs_baseline" in by_id:
        notes.append(_spo2(by_id["spo2_vs_baseline"]))
    if date == analysis.today_local():
        moving = _inactivity(conn, source, date, now)
        if moving:
            notes.append(moving)
    for extra in (_signal(conn, source, date), _wear(conn, source, date)):
        if extra:
            notes.append(extra)
    if not base_ready:
        info = analysis.baseline(conn, source, date, 7)
        base_ready = info["ready"]
        if not base_ready:
            notes.append(_item("baseline", "ok", "Baseline is being collected", info["reason"].capitalize() + ".",
                               "timeline.html", "hr-h", "ASTRA learns what is usual for you before it compares days.",
                               []))
    if date == analysis.today_local():
        space = radiation.notice_item(conn)
        if space:
            notes.append(space)
        early = outlook.notice_item(conn)
        if early and not (space and space["level"] != "ok" and space["id"] == "radiation"):
            notes.append(early)
    notes.sort(key=lambda n: LEVEL_ORDER[n["level"]])
    night = rest.night(conn, source, date)
    counts = {level: sum(1 for n in notes if n["level"] == level) for level in LEVEL_ORDER}
    return {"source": source, "date": date, "generated_at": now.isoformat(timespec="seconds"),
            "summary": counts, "notifications": notes,
            "suggestions": _suggestions(conn, source, date, notes, base_ready, night["status"] == "ok"),
            "disclaimer": DISCLAIMER}

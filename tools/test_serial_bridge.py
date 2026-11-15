"""Tests for tools/serial_bridge.py (run: pytest tools/test_serial_bridge.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serial_bridge as sb  # noqa: E402

GOOD = {"device_id": "ASTRA-01", "heart_rate_bpm": 72, "spo2_percent": None, "accel_x_g": 0.01, "accel_y_g": 0.02,
        "accel_z_g": 0.99, "gyro_x_dps": 0.1, "gyro_y_dps": 0.0, "gyro_z_dps": 0.2, "signal_quality": "good",
        "source": "live_hardware", "uptime_ms": 12000}


def test_a_measurement_line_is_parsed_unchanged():
    assert sb.parse_line("ASTRA_JSON " + json.dumps(GOOD) + "\r\n") == GOOD


def test_null_values_stay_null():
    p = sb.parse_line('ASTRA_JSON {"heart_rate_bpm":null,"signal_quality":"no_finger"}')
    assert p["heart_rate_bpm"] is None


def test_other_lines_are_ignored():
    for line in ("[PULSE] BPM: 71.0 | Average: 70.5", "", "ASTRA_JSON {broken", "ASTRA_JSON [1,2]", "ASTRA_JSON"):
        assert sb.parse_line(line) is None


def test_describe_shows_hr_signal_and_motion():
    text = sb.describe(GOOD, 201)
    assert "HR 72" in text and "signal good" in text and "accel 0.99 g" in text and "HTTP 201" in text
    assert "HR --" in sb.describe({**GOOD, "heart_rate_bpm": None}, 201)
    assert "accel --" in sb.describe({**GOOD, "accel_x_g": None}, 201)


# ---------- LCD messages ----------
def n(nid, level, title=""):
    return {"id": nid, "level": level, "title": title}


def test_every_lcd_line_fits_the_16_character_screen():
    cases = [n("hr_vs_baseline", "danger", "Heart rate higher than usual"), n("hr_vs_baseline", "warning", "Heart rate lower than usual"),
             n("spo2_vs_baseline", "warning", "Blood oxygen lower than usual"), n("inactivity", "warning"),
             n("rest_start_vs_usual", "warning"), n("rest_length_vs_usual", "warning", "Rest was shorter than usual"),
             n("signal_quality", "warning"), n("connection", "danger"), n("connection", "warning"),
             n("radiation_outlook", "warning", "Radiation watch: the Sun is active"), n("radiation_outlook", "warning", "Prepare"),
             n("radiation", "danger", "Shelter"), n("something_new", "warning", "A very long unknown notification title")]
    for c in cases:
        m = sb.lcd_message(c)
        assert m and all(len(line) <= 16 and line for line in m), (c, m)
        assert len(sb.format_msg(m).strip().split(" ", 1)[1]) <= 33


def test_only_warnings_and_dangers_are_shown_and_wear_time_is_skipped():
    assert sb.lcd_message(n("connection", "ok")) is None
    assert sb.lcd_message(n("wear_time", "warning")) is None
    assert sb.lcd_messages([n("hr_vs_baseline", "ok"), n("wear_time", "warning")]) == []


def test_heart_rate_direction_and_level():
    assert sb.lcd_message(n("hr_vs_baseline", "danger", "Heart rate higher than usual")) == ("HEART RATE HIGH", "Rest, tell crew")
    assert sb.lcd_message(n("hr_vs_baseline", "warning", "Heart rate lower than usual"))[0] == "HEART RATE LOW"


def test_format_msg_is_plain_ascii_and_empty_means_clear():
    assert sb.format_msg(("A|B é", "x")) == "ASTRA_MSG AB |x\n"
    assert sb.format_msg(None) == "ASTRA_MSG |\n"


def test_a_red_notification_is_the_only_one_on_the_lcd():
    red, orange = n("hr_vs_baseline", "danger", "Heart rate higher than usual"), n("inactivity", "warning")
    assert sb.lcd_messages([red, orange]) == [("HEART RATE HIGH", "Rest, tell crew")]
    two = sb.lcd_messages([red, n("connection", "danger"), orange])
    assert two == [("HEART RATE HIGH", "Rest, tell crew"), ("DATA STOPPED", "Check the link")]
    assert sb.lcd_messages([orange, n("signal_quality", "warning")]) == [("NO MOVEMENT", "Stand up, move"), ("WEAK SIGNAL", "Refit the sensor")]

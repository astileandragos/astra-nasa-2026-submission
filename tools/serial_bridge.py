"""ASTRA USB bridge: reads the measurement lines the ESP32 prints on its USB serial port and POSTs them to the dashboard.

Use it for the live demo when the board is plugged into the laptop (no Wi-Fi needed). The firmware must be built with
ENABLE_NETWORK 0 and USB_STREAM 1 (see firmware/esp32/README.md). It prints one line per measurement, for example
    ASTRA_JSON {"device_id":"ASTRA-01","heart_rate_bpm":72,...,"source":"live_hardware"}
and this script forwards the JSON to POST /api/measurements (docs/api_contract.md) exactly as it is. It never invents or
changes a value: a missing value stays null.

It also sends the current dashboard notification back to the board as "ASTRA_MSG <line 1>|<line 2>", which the board shows
on its 16x2 LCD (red notifications first; several are shown in turn). Use --no-lcd to turn this off.

    python tools/serial_bridge.py                 # finds the board by itself (CP210x / CH340 / USB serial)
    python tools/serial_bridge.py --port COM14
    python tools/serial_bridge.py --list          # show the serial ports and stop

Close the Arduino Serial Monitor first: only one program can open the port.
Needs: pip install pyserial requests
"""
import argparse
import json
import sys
import time

PREFIX = "ASTRA_JSON "
BOARD_HINTS = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "esp32", "ftdi")


def parse_line(line):
    """Return the payload dict for one serial line, or None when the line is not a measurement line."""
    line = line.strip()
    if not line.startswith(PREFIX):
        return None
    try:
        payload = json.loads(line[len(PREFIX):])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def describe(payload, status):
    """One short line for the terminal, so you can see at a glance that data is flowing."""
    hr = payload.get("heart_rate_bpm")
    parts = [time.strftime("%H:%M:%S"), "HR " + ("--" if hr is None else str(hr)), "signal " + str(payload.get("signal_quality"))]
    try:
        g = (payload["accel_x_g"] ** 2 + payload["accel_y_g"] ** 2 + payload["accel_z_g"] ** 2) ** 0.5
        parts.append("accel %.2f g" % g)
    except (KeyError, TypeError):
        parts.append("accel --")
    parts.append("-> HTTP %s" % status)
    return "  ".join(parts)


LCD_WIDTH = 16          # the 16x2 LCD: two lines of 16 characters
SKIP_ON_LCD = {"wear_time"}   # housekeeping notice, not worth the small screen


def _word(title, up, down):
    t = title.lower()
    return up if ("higher" in t or "longer" in t or "more" in t) else down if ("lower" in t or "shorter" in t) else up


def lcd_message(n):
    """Two 16-character lines for one dashboard notification, or None when it should not be shown on the LCD.
    The wording follows the dashboard advice (short version): self-care first, crew for the red level."""
    level, nid, title = n.get("level"), n.get("id"), n.get("title", "")
    if level not in ("warning", "danger") or nid in SKIP_ON_LCD:
        return None
    red = level == "danger"
    if nid == "hr_vs_baseline":
        return ("HEART RATE " + _word(title, "HIGH", "LOW"), "Rest, tell crew" if red else "Sit down, rest")
    if nid == "spo2_vs_baseline":
        return ("OXYGEN " + _word(title, "HIGH", "LOW"), "Sit up, breathe")
    if nid == "inactivity":
        return ("NO MOVEMENT", "Stand up, move")
    if nid == "rest_start_vs_usual":
        return ("REST TIME OFF", "Rest on schedule")
    if nid == "rest_length_vs_usual":
        return ("REST " + ("LONG" if "longer" in title.lower() else "SHORT"), "Keep rest steady")
    if nid == "signal_quality":
        return ("WEAK SIGNAL", "Refit the sensor")
    if nid == "connection":
        return ("DATA STOPPED" if red else "NO NEW DATA", "Check the link")
    if nid == "radiation_outlook":
        return ("RADIATION PREP" if "prepare" in title.lower() else "RADIATION WATCH",
                "Get ready now" if "prepare" in title.lower() else "Stay informed")
    if nid and nid.startswith("radiation"):
        return ("RADIATION ALERT", "Follow the plan")
    return (title.upper()[:LCD_WIDTH], "See dashboard")


def lcd_messages(notifications):
    """Messages for the LCD, without duplicates. While any notification is red, ONLY the red ones are shown (several reds
    rotate); the orange ones come back when no red is left."""
    reds = [n for n in notifications if n.get("level") == "danger"]
    if any(lcd_message(n) for n in reds):
        notifications = reds
    out = []
    for n in notifications:
        m = lcd_message(n)
        if m and m not in out:
            out.append(m)
    return out


def format_msg(message):
    """The serial line for the board. Plain ASCII, 16 characters per line, no '|' inside. None = clear the message."""
    l1, l2 = message if message else ("", "")
    clean = lambda s: "".join(c for c in s if 32 <= ord(c) < 127 and c != "|")[:LCD_WIDTH]
    return "ASTRA_MSG %s|%s\n" % (clean(l1), clean(l2))


def fetch_notifications(url):
    import requests
    try:
        return requests.get(url, timeout=2.0).json().get("notifications", [])
    except (requests.RequestException, ValueError):
        return []


def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        text = ("%s %s" % (p.description, p.manufacturer or "")).lower()
        if any(h in text for h in BOARD_HINTS):
            return p.device
    return None


def post(url, payload, timeout=2.0):
    import requests
    try:
        return requests.post(url, json=payload, timeout=timeout).status_code
    except requests.RequestException as exc:
        return "error (%s)" % type(exc).__name__


REFRESH_S = 3.0     # ask the dashboard for notifications this often
ROTATE_S = 4.0      # when there are several notifications, show each for this long
RESEND_S = 2.0      # repeat the current message (the board forgets it after 8 s without a refresh)


def run(port, baud, url, verbose=False, lcd=True):
    import serial
    notif_url = url.replace("/api/measurements", "/api/notifications?source=dashboard")
    msgs, shown, last_fetch, last_send, last_rotate, last_text = [], 0, 0.0, 0.0, 0.0, None
    while True:
        try:
            with serial.Serial(port, baud, timeout=1) as ser:
                print("Reading %s at %d baud. Posting to %s.%s Ctrl+C to stop." % (port, baud, url, " LCD notifications on." if lcd else ""))
                while True:
                    now = time.time()
                    if lcd:
                        if now - last_fetch >= REFRESH_S:
                            last_fetch, msgs = now, lcd_messages(fetch_notifications(notif_url))
                        if now - last_rotate >= ROTATE_S:
                            last_rotate, shown = now, shown + 1
                        message = msgs[shown % len(msgs)] if msgs else None
                        if now - last_send >= RESEND_S or message != last_text:
                            changed = message != last_text
                            last_send, last_text = now, message
                            ser.write(format_msg(message).encode("ascii"))
                            if changed and message:
                                print("   LCD:", " / ".join(message))
                    raw = ser.readline().decode("utf-8", errors="replace")
                    if not raw:
                        continue
                    payload = parse_line(raw)
                    if payload is None:
                        if verbose and raw.strip():
                            print("   board:", raw.strip())
                        continue
                    print(describe(payload, post(url, payload)))
        except serial.SerialException as exc:
            print("Cannot use %s (%s). Is the Serial Monitor still open? Retrying in 3 s..." % (port, exc))
            time.sleep(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", help="serial port, for example COM14 (default: find the board)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--url", default="http://127.0.0.1:5000/api/measurements")
    ap.add_argument("--no-lcd", action="store_true", help="do not send dashboard notifications to the board LCD")
    ap.add_argument("--list", action="store_true", help="list the serial ports and exit")
    ap.add_argument("--verbose", action="store_true", help="also print the other lines the board writes")
    args = ap.parse_args()

    if args.list:
        from serial.tools import list_ports
        for p in list_ports.comports():
            print(p.device, "-", p.description)
        return 0
    port = args.port or find_port()
    if not port:
        print("No board found. Plug it in, or pass --port COMx (use --list to see the ports).")
        return 1
    try:
        run(port, args.baud, args.url, args.verbose, lcd=not args.no_lcd)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

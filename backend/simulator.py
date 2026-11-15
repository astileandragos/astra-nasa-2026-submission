"""Posts fake measurements every 2 seconds. Every record is labelled "simulated".

Usage (from backend/):  python simulator.py [--url URL] [--interval SECONDS]
Stop with Ctrl+C. The values are random demo data, not real measurements.
"""
import argparse
import random
import time

import requests

DEFAULT_URL = "http://127.0.0.1:5000/api/measurements"


def make_payload(uptime_ms):
    # Occasionally act like "no finger on the MAX30102": heart rate and SpO2 are null.
    no_finger = random.random() < 0.1
    return {
        "device_id": "SIM-01",
        "heart_rate_bpm": None if no_finger else random.randint(60, 90),
        "spo2_percent": None if no_finger else random.randint(95, 99),
        "accel_x_g": round(random.uniform(-0.05, 0.05), 3),
        "accel_y_g": round(random.uniform(-0.05, 0.05), 3),
        "accel_z_g": round(random.uniform(0.95, 1.05), 3),
        "gyro_x_dps": round(random.uniform(-1, 1), 2),
        "gyro_y_dps": round(random.uniform(-1, 1), 2),
        "gyro_z_dps": round(random.uniform(-1, 1), 2),
        "signal_quality": "no_finger" if no_finger else "good",
        "source": "simulated",  # hard-coded: never live_hardware
        "uptime_ms": uptime_ms,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    start = time.monotonic()
    while True:
        payload = make_payload(int((time.monotonic() - start) * 1000))
        try:
            r = requests.post(args.url, json=payload, timeout=5)
            print(r.status_code, r.json())
        except requests.RequestException as err:
            print("could not reach the server:", err)
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")

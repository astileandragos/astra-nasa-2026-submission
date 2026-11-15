"""Fill the database with several days of SIMULATED data so the analysis can be shown without hardware.

Usage (from backend/):
    python seed_demo.py                    # 6 earlier days + today, today's heart rate a bit higher
    python seed_demo.py --today normal     # today looks like the other days (also: elevated, lower)
    python seed_demo.py --late-bed         # last night's rest starts about 2 hours later than usual
    python seed_demo.py --low-spo2         # today's SpO2 about 4 points under the usual
    python seed_demo.py --baseline-week --days 7   # PITCH: a simulated week, today stays empty for the live sensor
    python seed_demo.py --clear            # only remove the seeded data

Everything written here is labelled "simulated" (device SEED-SIM, check-ins with source simulated).
It never writes live_hardware rows, and it only deletes its own rows, so it is safe to run again.
The numbers are random demo values, not real measurements.
"""
import argparse
import random
from datetime import datetime, timedelta

from app import DB_PATH, get_db, init_db

DEVICE = "SEED-SIM"


def clear(conn):
    m = conn.execute("DELETE FROM measurements WHERE device_id = ? AND source = 'simulated'", (DEVICE,)).rowcount
    j = conn.execute("DELETE FROM journal WHERE source = 'simulated'").rowcount
    return m, j


def make_nights(rng, days, today_mode, late_bed):
    """Bedtime (hour of the evening) and length (hours) of the night that starts on each day, `back` days ago."""
    bed, length = {}, {}
    for back in range(days + 1, -1, -1):
        bed[back] = min(max(rng.gauss(23.0, 0.6), 21.75), 23.75)
        length[back] = min(max(rng.gauss(7.0, 0.5), 5.5), 8.5)
    length[1] = {"normal": length[1], "elevated": 4.5, "lower": 9.5}[today_mode]   # the night that ends today
    if late_bed:
        bed[1] += 2.0
    return bed, length


def is_asleep(bed, length, back, hour):
    """Simulated resting: the night ending on this day, or the night starting this evening."""
    b = bed[back + 1]
    wake = b + length[back + 1] - 24
    if (b - 24 <= hour < wake) if b >= 24 else hour < wake:
        return True
    return bed[back] < 24 and hour >= bed[back]


def reading(rng, moment, hr_offset, asleep, spo2_drop=0):
    hour = moment.hour + moment.minute / 60
    moving = rng.random() < (0.02 if asleep else 0.7)     # a few short movements while resting
    if moving:
        ax, ay, az = (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0.8, 1.25))
        gx, gy, gz = (rng.uniform(-40, 40) for _ in range(3))
    else:
        ax, ay, az = (rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), rng.uniform(0.98, 1.02))
        gx, gy, gz = (rng.uniform(-1, 1) for _ in range(3))
    hr = 66 + hr_offset + (-6 if asleep else 4 if 9 <= hour < 18 else 2) + (6 if moving else 0) + rng.gauss(0, 2)
    roll = rng.random()
    quality = "good" if roll < 0.88 else "poor" if roll < 0.95 else "no_finger"
    no_value = quality == "no_finger"
    return {
        "heart_rate_bpm": None if no_value else round(hr),
        "spo2_percent": None if no_value else min(99, max(88, round(97 - spo2_drop + rng.gauss(0, 1)))),
        "accel_x_g": round(ax, 3), "accel_y_g": round(ay, 3), "accel_z_g": round(az, 3),
        "gyro_x_dps": round(gx, 2), "gyro_y_dps": round(gy, 2), "gyro_z_dps": round(gz, 2),
        "signal_quality": quality,
    }


def seed(conn, days, today_mode, rng, late_bed=False, low_spo2=False, skip_today=False):
    now = datetime.now().astimezone().replace(microsecond=0)
    start_of_today = now.replace(hour=0, minute=0, second=0)
    rows = journal = 0
    bed, length = make_nights(rng, days, today_mode, late_bed)
    for back in range(days, -1, -1):  # oldest earlier day first, today last
        day_start = start_of_today - timedelta(days=back)
        is_today = back == 0
        if is_today and skip_today:
            continue      # the pitch: today is filled by the live sensor
        offset = rng.gauss(0, 1.2)
        sleep = length[back + 1]     # reported sleep follows the simulated night that ends on this day
        if is_today:
            offset = {"normal": rng.gauss(0, 1.2), "elevated": 9.0, "lower": -9.0}[today_mode]
        step = timedelta(seconds=30) if is_today else timedelta(minutes=15)
        moment = day_start
        while moment <= (now if is_today else day_start + timedelta(hours=23, minutes=59)):
            r = reading(rng, moment, offset, is_asleep(bed, length, back, moment.hour + moment.minute / 60),
                        spo2_drop=4 if (low_spo2 and is_today) else 0)
            conn.execute(
                "INSERT INTO measurements (received_at, device_id, heart_rate_bpm, spo2_percent, accel_x_g, "
                "accel_y_g, accel_z_g, gyro_x_dps, gyro_y_dps, gyro_z_dps, signal_quality, source, uptime_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'simulated',NULL)",
                (moment.isoformat(timespec="seconds"), DEVICE, r["heart_rate_bpm"], r["spo2_percent"],
                 r["accel_x_g"], r["accel_y_g"], r["accel_z_g"], r["gyro_x_dps"], r["gyro_y_dps"],
                 r["gyro_z_dps"], r["signal_quality"]))
            rows += 1
            moment += step
        conn.execute(
            "INSERT OR IGNORE INTO journal (date, received_at, sleep_hours, mood, energy, stress, fatigue, note, source) "
            "VALUES (?,?,?,?,?,?,?,NULL,'simulated')",
            (day_start.date().isoformat(), now.isoformat(timespec="seconds"), None,      # sleep is estimated from movement, not typed in
             rng.randint(2, 4), rng.randint(2, 4), rng.randint(2, 4), rng.randint(2, 4)))
        journal += 1
    return rows, journal


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=6, help="earlier days to create (default 6)")
    parser.add_argument("--today", choices=["normal", "elevated", "lower"], default="elevated")
    parser.add_argument("--late-bed", action="store_true", help="last night starts about 2 hours later")
    parser.add_argument("--low-spo2", action="store_true", help="today's SpO2 is about 4 points lower than usual")
    parser.add_argument("--baseline-week", action="store_true", help="pitch setup: 7 earlier days and nothing for today (the live sensor fills today)")
    parser.add_argument("--seed", type=int, default=42, help="random seed, same seed = same data")
    parser.add_argument("--clear", action="store_true", help="only remove the seeded data")
    args = parser.parse_args()
    init_db()
    with get_db() as conn:
        removed = clear(conn)
        print(f"Removed {removed[0]} seeded measurements and {removed[1]} seeded check-ins.")
        if not args.clear:
            rows, journal = seed(conn, args.days, args.today, random.Random(args.seed), args.late_bed, args.low_spo2, args.baseline_week)
            print(f"Added {rows} simulated measurements and {journal} simulated check-ins to {DB_PATH}.")
            print("All labelled 'simulated'. Open the dashboard with ?source=simulated.")


if __name__ == "__main__":
    main()

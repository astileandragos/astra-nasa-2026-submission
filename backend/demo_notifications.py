"""Fill today with SIMULATED problems so every notification and its advice text can be checked on the dashboard.

Usage (from backend/, with the simulator stopped):  python demo_notifications.py
It replaces today's simulated readings and the seeded earlier days (device SEED-SIM) and starts the radiation demo
scenario "prepare". Only simulated rows are touched; live_hardware rows are never changed. Run it again to refresh
(the connection and movement notices depend on how old the last reading is).

What it creates for today: heart rate far above the usual, blood oxygen below the usual, last night's rest starting
late and short, many poor-signal readings, a 3-hour gap in the data, no movement for the last 90 minutes, no check-in,
a last reading that is 20 seconds old (it turns into "Data stopped" after 5 minutes) and a radiation "prepare" stage.
"""
import random
from datetime import datetime, timedelta

import radiation
import seed_demo
from app import get_db, init_db


def main():
    init_db()
    now = datetime.now().astimezone()
    today = now.date().isoformat()
    cutoff = (now - timedelta(seconds=20)).isoformat(timespec="seconds")
    still_from = (now - timedelta(minutes=90)).isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("DELETE FROM measurements WHERE source = 'simulated' AND substr(received_at, 1, 10) >= ?", (today,))
        seed_demo.clear(conn)
        seed_demo.seed(conn, 6, "elevated", random.Random(42), late_bed=True, low_spo2=True)
        conn.execute("DELETE FROM journal WHERE date >= ?", (today,))                                    # no check-in today
        conn.execute("DELETE FROM measurements WHERE source = 'simulated' AND received_at > ?", (cutoff,))
        conn.execute("DELETE FROM measurements WHERE source = 'simulated' AND substr(received_at, 1, 10) = ? "
                     "AND substr(received_at, 12, 5) BETWEEN '06:30' AND '09:30'", (today,))             # a 3-hour gap
        conn.execute("UPDATE measurements SET signal_quality = 'poor' WHERE source = 'simulated' "
                     "AND substr(received_at, 1, 10) = ? AND id % 5 < 2", (today,))                       # 40% poor signal
        conn.execute("UPDATE measurements SET accel_x_g = 0, accel_y_g = 0, accel_z_g = 1, gyro_x_dps = 0, gyro_y_dps = 0, "
                     "gyro_z_dps = 0 WHERE source = 'simulated' AND received_at >= ?", (still_from,))     # no movement
        conn.execute("UPDATE measurements SET heart_rate_bpm = heart_rate_bpm + 18 WHERE source = 'simulated' "
                     "AND substr(received_at, 1, 10) = ? AND heart_rate_bpm IS NOT NULL", (today,))      # heart rate far above usual
        radiation.simulate(conn, "prepare")
        left = conn.execute("SELECT COUNT(*) FROM measurements WHERE source = 'simulated' AND substr(received_at, 1, 10) = ?",
                            (today,)).fetchone()[0]
    print(f"Done: {left} simulated readings today, last one at {cutoff}. Open the dashboard Overview and the Sensors, Activity and Radiation pages.")


if __name__ == "__main__":
    main()

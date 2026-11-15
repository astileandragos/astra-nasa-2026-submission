"""ASTRA backend: Flask + SQLite. Follows docs/api_contract.md.

Run from backend/:  python app.py   (listens on 0.0.0.0:5000)
"""
import csv
import io
import logging
import os
import re
import sqlite3
import statistics
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

import analysis
import notices
import osdr
import outlook
import radiation
import reference
import rest

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ASTRA_DB", BASE_DIR / "astra.db"))
SCHEMA_PATH = BASE_DIR / "schema.sql"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

SOURCES = {"live_hardware", "self_reported", "simulated", "external"}
QUALITIES = {"good", "poor", "no_finger", "unknown"}

# Sanity limits: reject impossible values only. These are NOT health thresholds.
# (field, minimum, maximum, minimum is exclusive)
SENSOR_LIMITS = {
    "heart_rate_bpm": (0, 300, True),
    "spo2_percent": (0, 100, True),
    "accel_x_g": (-16, 16, False),
    "accel_y_g": (-16, 16, False),
    "accel_z_g": (-16, 16, False),
    "gyro_x_dps": (-2000, 2000, False),
    "gyro_y_dps": (-2000, 2000, False),
    "gyro_z_dps": (-2000, 2000, False),
}
COLUMNS = ["device_id", *SENSOR_LIMITS, "signal_quality", "source", "uptime_ms"]
READ_COLUMNS = ", ".join(["id", "received_at", *COLUMNS])
JOURNAL_ANSWERS = ["sleep_hours", "mood", "energy", "stress", "fatigue"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_LIMIT = 50
MAX_LIMIT = 100


class ValidationError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def get_db(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Create the tables if they do not exist."""
    with get_db(db_path) as conn:
        # WAL: the ESP32 can write while the dashboard reads, without "database is locked" errors.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Databases created before the journal had a source column get it added (old rows are self_reported).
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(journal)")]
        if "source" not in columns:
            conn.execute("ALTER TABLE journal ADD COLUMN source TEXT NOT NULL DEFAULT 'self_reported'")


def is_number(value):
    # bool is a subclass of int in Python; a JSON true/false is not a number.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_measurement(data):
    """Return a clean dict ready to insert, or raise ValidationError."""
    if not isinstance(data, dict):
        raise ValidationError("body must be a JSON object")

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValidationError("device_id is required and must be a non-empty string", "device_id")

    source = data.get("source")
    if source not in SOURCES:
        raise ValidationError(f"source must be one of {sorted(SOURCES)}", "source")

    clean = {"device_id": device_id.strip(), "source": source}

    for field, (low, high, low_exclusive) in SENSOR_LIMITS.items():
        value = data.get(field)  # absent counts as null
        if value is None:
            clean[field] = None
            continue
        if not is_number(value):
            raise ValidationError(f"{field} must be a number or null", field)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidationError(f"{field} must be a finite number or null", field)
        if field in ("heart_rate_bpm", "spo2_percent") and value == 0:
            raise ValidationError("Use null for missing values, not 0", field)
        too_low = value <= low if low_exclusive else value < low
        if too_low or value > high:
            raise ValidationError(f"{field} is outside the allowed range ({low} to {high})", field)
        clean[field] = value

    quality = data.get("signal_quality", "unknown")
    if quality is None:
        quality = "unknown"
    if quality not in QUALITIES:
        raise ValidationError(f"signal_quality must be one of {sorted(QUALITIES)}", "signal_quality")
    clean["signal_quality"] = quality

    uptime = data.get("uptime_ms")
    if uptime is not None:
        if not isinstance(uptime, int) or isinstance(uptime, bool) or uptime < 0:
            raise ValidationError("uptime_ms must be a non-negative integer or null", "uptime_ms")
    clean["uptime_ms"] = uptime
    return clean


def setup_logging(app, log_path):
    """Log warnings (bad requests) and errors to the console and to a rotating file."""
    app.logger.setLevel(logging.INFO)
    for old in [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)]:
        app.logger.removeHandler(old)   # one file handler at a time, always the newest path
        old.close()
    if log_path is None:
        return
    handler = RotatingFileHandler(log_path, maxBytes=500_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app.logger.addHandler(handler)


def csv_safe(value):
    """Stop spreadsheet programs from running text that starts with = + - @ as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def arg_source(default="live_hardware"):
    source = request.args.get("source", default)
    if source not in SOURCES and source != analysis.DASHBOARD:
        raise ValidationError(f"source must be one of {sorted(SOURCES)}", "source")
    return source


def arg_date():
    value = request.args.get("date")
    if value is None:
        return analysis.today_local()
    try:
        if not DATE_RE.match(value):
            raise ValueError
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("date must be a real date like 2026-11-14", "date")
    return value


def arg_int(name, default, low, high):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError(f"{name} must be a whole number", name)
    if value < low or value > high:
        raise ValidationError(f"{name} must be between {low} and {high}", name)
    return value


def validate_journal(data):
    """Return a clean journal entry, or raise ValidationError (contract section 6.5)."""
    if not isinstance(data, dict):
        raise ValidationError("body must be a JSON object")
    date_text = data.get("date")
    if not isinstance(date_text, str) or not DATE_RE.match(date_text):
        raise ValidationError("date is required and must look like 2026-11-14", "date")
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("date is not a real calendar date", "date")

    clean = {"date": date_text}
    sleep = data.get("sleep_hours")
    if sleep is not None:
        if not is_number(sleep) or sleep != sleep:
            raise ValidationError("sleep_hours must be a number or null", "sleep_hours")
        if sleep < 0 or sleep > 24:
            raise ValidationError("sleep_hours must be between 0 and 24", "sleep_hours")
    clean["sleep_hours"] = sleep

    for field in ("mood", "energy", "stress", "fatigue"):
        value = data.get(field)
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValidationError(f"{field} must be a whole number from 1 to 5, or null", field)
            if value < 1 or value > 5:
                raise ValidationError(f"{field} must be between 1 and 5 (use null to skip, not 0)", field)
        clean[field] = value

    note = data.get("note")
    if note is not None:
        if not isinstance(note, str):
            raise ValidationError("note must be text or null", "note")
        if len(note) > 500:
            raise ValidationError("note must be at most 500 characters", "note")
        note = note.strip() or None
    clean["note"] = note

    if all(clean[f] is None for f in JOURNAL_ANSWERS):
        raise ValidationError("answer at least one of sleep_hours, mood, energy, stress, fatigue")
    return clean


def create_app(db_path=None, frontend_dir=None, log_path=None, reference_path=None, noaa_fetch=None,
               noaa_background=False, osdr_fetch=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DB_PATH
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024   # a measurement is a few hundred bytes
    reference_file = Path(reference_path or reference.DEFAULT_PATH)
    setup_logging(app, log_path)
    frontend = Path(frontend_dir or FRONTEND_DIR)
    init_db(app.config["DB_PATH"])
    # Local demo only: lets a page opened from another origin (a file, Live Server) call the API.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.errorhandler(ValidationError)
    def handle_validation(err):
        # Log what was wrong, never the body (journal notes can be personal).
        app.logger.warning("rejected %s %s from %s: %s%s", request.method, request.path, request.remote_addr,
                           err.message, f" (field {err.field})" if err.field else "")
        body = {"status": "error", "message": err.message}
        if err.field:
            body["field"] = err.field
        return jsonify(body), 400

    @app.errorhandler(404)
    def handle_404(_err):
        return jsonify({"status": "error", "message": "not found"}), 404

    @app.errorhandler(413)
    def handle_413(_err):
        return jsonify({"status": "error", "message": "request body too large"}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        if isinstance(getattr(err, "code", None), int) and err.code < 500:
            return err  # normal HTTP errors keep their own answer
        app.logger.exception("unexpected error on %s %s", request.method, request.path)
        return jsonify({"status": "error", "message": "internal server error"}), 500

    @app.errorhandler(405)
    def handle_405(_err):
        return jsonify({"status": "error", "message": "method not allowed"}), 405

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/measurements")
    def post_measurement():
        data = request.get_json(silent=True)
        if data is None:
            raise ValidationError("body must be valid JSON with Content-Type: application/json")
        clean = validate_measurement(data)
        received_at = datetime.now().astimezone().isoformat(timespec="seconds")
        columns = ["received_at", *COLUMNS]
        values = [received_at, *(clean[c] for c in COLUMNS)]
        sql = f"INSERT INTO measurements ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})"
        try:
            with get_db(app.config["DB_PATH"]) as conn:
                cur = conn.execute(sql, values)
        except sqlite3.Error:
            app.logger.exception("could not save measurement")
            return jsonify({"status": "error", "message": "could not save the measurement"}), 500
        return jsonify({"status": "ok", "id": cur.lastrowid, "received_at": received_at}), 201

    @app.get("/api/measurements/latest")
    def latest_measurement():
        sql = f"SELECT {READ_COLUMNS} FROM measurements"
        params = []
        with get_db(app.config["DB_PATH"]) as conn:
            if request.args.get("source") is not None:
                where, params = analysis.source_where(conn, arg_source())
                sql += f" WHERE {where}"
            row = conn.execute(sql + " ORDER BY received_at DESC, id DESC LIMIT 1", params).fetchone()
        if row is None:
            return jsonify({"status": "error", "message": "no measurements yet"}), 404
        return jsonify(dict(row))

    @app.get("/api/measurements")
    def list_measurements():
        raw_limit = request.args.get("limit", str(DEFAULT_LIMIT))
        try:
            limit = int(raw_limit)
        except ValueError:
            raise ValidationError("limit must be a whole number", "limit")
        if limit < 1:
            raise ValidationError("limit must be at least 1", "limit")
        limit = min(limit, MAX_LIMIT)

        where, params = [], []
        source = request.args.get("source")
        if source is not None:
            if source not in SOURCES and source != analysis.DASHBOARD:
                raise ValidationError(f"source must be one of {sorted(SOURCES)} or dashboard", "source")
            if source != analysis.DASHBOARD:
                where.append("source = ?")
                params.append(source)

        since = request.args.get("since")
        if since is not None:
            # A "+" in a URL query turns into a space, so put it back.
            try:
                since_dt = datetime.fromisoformat(since.strip().replace(" ", "+"))
            except ValueError:
                raise ValidationError("since must be an ISO 8601 time, for example 2026-11-14T12:30:00+02:00", "since")
            if since_dt.tzinfo is None:
                since_dt = since_dt.astimezone()  # no zone given: assume this laptop's time zone
            where.append("julianday(received_at) > julianday(?)")  # compares real instants, not text
            params.append(since_dt.isoformat())

        with get_db(app.config["DB_PATH"]) as conn:
            if source == analysis.DASHBOARD:
                where_sql, where_params = analysis.source_where(conn, source)
                where.append(where_sql)
                params = [*params, *where_params]
            sql = f"SELECT {READ_COLUMNS} FROM measurements"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY received_at DESC, id DESC LIMIT ?"
            rows = conn.execute(sql, [*params, limit]).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/api/quality")
    def quality():
        source, date, days = arg_source(), arg_date(), arg_int("days", 7, 1, 30)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(analysis.quality(conn, source, date, days))

    @app.get("/api/stats/daily")
    def stats_daily():
        source, date, days = arg_source(), arg_date(), arg_int("days", 7, 1, 30)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(analysis.daily_stats(conn, source, date, days))

    @app.get("/api/baseline")
    def baseline():
        source, date, days = arg_source(), arg_date(), arg_int("days", 7, 1, 30)
        with get_db(app.config["DB_PATH"]) as conn:
            result = analysis.baseline(conn, source, date, days)
        result.pop("_usable_days", None)
        return jsonify(result)

    # The analysis endpoints are heavy (several days of readings) and the pages ask for them every few seconds: the answer
    # is computed once and reused for a few seconds (see analysis.memo).
    def cached(conn, compute):
        return jsonify(analysis.memo(conn, ("http", request.full_path), compute))

    @app.get("/api/observation")
    def observation():
        source, date = arg_source(), arg_date()
        with get_db(app.config["DB_PATH"]) as conn:
            return cached(conn, lambda: analysis.observation(conn, source, date))

    @app.get("/api/activity")
    def activity():
        source, date, window = arg_source(), arg_date(), arg_int("window_min", 30, 5, 120)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(analysis.activity(conn, source, date, window))

    @app.get("/api/timeline")
    def timeline():
        source, date, days = arg_source(), arg_date(), arg_int("days", 7, 1, 30)
        with get_db(app.config["DB_PATH"]) as conn:
            return cached(conn, lambda: analysis.timeline(conn, source, date, days))

    @app.get("/api/rest")
    def rest_periods():
        source, date, nights = arg_source(), arg_date(), arg_int("nights", 7, 1, 14)
        with get_db(app.config["DB_PATH"]) as conn:
            return cached(conn, lambda: rest.rest(conn, source, date, nights))

    @app.get("/api/wear")
    def wear_time():
        source, date, days = arg_source(), arg_date(), arg_int("days", 7, 1, 30)
        with get_db(app.config["DB_PATH"]) as conn:
            return cached(conn, lambda: rest.wear(conn, source, date, days))

    @app.get("/api/notifications")
    def notifications():
        source, date = arg_source(), arg_date()
        with get_db(app.config["DB_PATH"]) as conn:
            return cached(conn, lambda: notices.compute(conn, source, date))

    # ---- Radiation Risk Monitor (contract 6.15) ----
    def arg_rad_source():
        source = request.args.get("source", "external")
        if source not in radiation.SOURCES:
            raise ValidationError(f"source must be one of {list(radiation.SOURCES)}", "source")
        return source

    def body_object():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValidationError("body must be a JSON object")
        return data

    def rad_call(func, *args):
        try:
            return func(*args)
        except ValueError as err:
            raise ValidationError(str(err))

    def keep_fresh(source):
        """Real data: refresh NOAA in the background when the last attempt is older than a minute."""
        if source == "external" and noaa_background:
            with get_db(app.config["DB_PATH"]) as conn:
                due = radiation.refresh_due(conn)
            if due:
                radiation.refresh_in_background(lambda: get_db(app.config["DB_PATH"]), noaa_fetch)

    @app.get("/api/radiation/status")
    def radiation_status():
        source = arg_rad_source()
        keep_fresh(source)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(radiation.status(conn, source))

    @app.get("/api/radiation/outlook")
    def radiation_outlook():
        """The staged heads-up: clear, watch, prepare, build the shelter, shelter, with what to do at each stage."""
        source = arg_rad_source()
        keep_fresh(source)
        extras = outlook.get_extras(noaa_fetch) if source == "external" and noaa_background else None
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(outlook.outlook(conn, source, extras))

    @app.get("/api/radiation/flux")
    def radiation_flux():
        source, hours = arg_rad_source(), arg_int("hours", 24, 1, 168)
        keep_fresh(source)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(radiation.history(conn, source, hours))

    @app.get("/api/radiation/events")
    def radiation_events():
        source, days = arg_rad_source(), arg_int("days", 7, 1, 7)
        keep_fresh(source)
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(radiation.events_and_alerts(conn, source, days))

    @app.get("/api/radiation/alert")
    def radiation_alert():
        """Compact answer for the ESP32 OLED: 4 short lines, a footer and a beep pattern."""
        source = arg_rad_source()
        keep_fresh(source)
        with get_db(app.config["DB_PATH"]) as conn:
            full = radiation.status(conn, source)
        pending = full["ack_pending"]
        return jsonify({"source": source, "level": full["state"]["level"], "s_class": full["state"]["s_class_now"],
                        "data_status": full["data_status"], "alert_id": pending["alert_id"] if pending else None,
                        "ack_pending": pending is not None, **full["oled"], "updated_at": full["generated_at"]})

    @app.post("/api/radiation/ack")
    def radiation_ack():
        alert_id = body_object().get("alert_id")
        if not isinstance(alert_id, str) or not alert_id:
            raise ValidationError("alert_id is required", "alert_id")
        with get_db(app.config["DB_PATH"]) as conn:
            item = radiation.acknowledge(conn, alert_id)
        if item is None:
            return jsonify({"status": "error", "message": "unknown alert_id"}), 404
        return jsonify({"status": "ok", "alert": item})

    @app.post("/api/radiation/refresh")
    def radiation_refresh():
        with get_db(app.config["DB_PATH"]) as conn:
            result = radiation.refresh_external(conn, noaa_fetch)
        return jsonify(result), (200 if result["error"] is None else 502)

    @app.post("/api/radiation/simulate")
    def radiation_simulate():
        data = body_object()
        with get_db(app.config["DB_PATH"]) as conn:
            if "scenario" in data:
                return jsonify(rad_call(radiation.simulate, conn, data["scenario"])), 201
            if "flux_pfu" in data:
                return jsonify(rad_call(radiation.add_simulated_sample, conn, data["flux_pfu"])), 201
        raise ValidationError("send {\"scenario\": \"quiet|watch|prepare|s1|s2|s3|s4|history\"} or {\"flux_pfu\": number}")

    @app.get("/api/radiation/budget")
    def radiation_budget():
        source = arg_rad_source()
        with get_db(app.config["DB_PATH"]) as conn:
            return jsonify(radiation.budget(conn, source))

    @app.post("/api/radiation/budget")
    def radiation_budget_settings():
        source, data = arg_rad_source(), body_object()
        with get_db(app.config["DB_PATH"]) as conn:
            rad_call(radiation.set_config, conn, source, data)
            return jsonify(radiation.budget(conn, source))

    @app.post("/api/radiation/dose")
    def radiation_dose():
        source, data = arg_rad_source(), body_object()
        with get_db(app.config["DB_PATH"]) as conn:
            rad_call(radiation.add_operator_dose, conn, source, data.get("msv"), data.get("note"))
            return jsonify(radiation.budget(conn, source)), 201

    @app.get("/api/status")
    def status():
        """Freshness of the data, for an offline or stale warning on the dashboard."""
        source = arg_source()
        stale_after = arg_int("stale_after", 10, 1, 3600)
        with get_db(app.config["DB_PATH"]) as conn:
            where, w_params = analysis.source_where(conn, source)
            total = conn.execute(f"SELECT COUNT(*) FROM measurements WHERE {where}", w_params).fetchone()[0]
            rows = conn.execute(f"SELECT received_at, signal_quality FROM measurements WHERE {where} "
                                "ORDER BY received_at DESC, id DESC LIMIT 50", w_params).fetchall()
        now = datetime.now().astimezone()
        last = rows[0]["received_at"] if rows else None
        seconds = None
        if last:
            seconds = max(0.0, round((now - datetime.fromisoformat(last)).total_seconds(), 1))
        times = [datetime.fromisoformat(r["received_at"]) for r in reversed(rows)]
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        return jsonify({
            "source": source, "server_time": now.isoformat(timespec="seconds"), "total": total,
            "last_received_at": last, "seconds_since_last": seconds,
            "latest_signal_quality": rows[0]["signal_quality"] if rows else None,
            "median_interval_seconds": round(statistics.median(gaps), 1) if gaps else None,
            "stale_after_seconds": stale_after,
            "stale": seconds is None or seconds > stale_after,
        })

    @app.get("/api/demo/status")
    def demo_status():
        """What the dashboard view is made of: the simulated baseline week and today's live (or simulator) readings."""
        today = analysis.today_local()
        with get_db(app.config["DB_PATH"]) as conn:
            today_src = analysis.today_source(conn)
            days = conn.execute("SELECT COUNT(DISTINCT substr(received_at, 1, 10)) FROM measurements "
                                "WHERE source = 'simulated' AND substr(received_at, 1, 10) < ?", (today,)).fetchone()[0]
            readings = conn.execute("SELECT COUNT(*) FROM measurements WHERE source = ? AND substr(received_at, 1, 10) = ?",
                                    (today_src, today)).fetchone()[0]
        return jsonify({"date": today, "baseline_source": "simulated", "baseline_days": days,
                        "today_source": today_src, "today_readings": readings})

    @app.post("/api/demo/reset-today")
    def demo_reset_today():
        """Start the live demo again: removes today's readings and today's check-in. Earlier days are never touched."""
        today = analysis.today_local()
        with get_db(app.config["DB_PATH"]) as conn:
            m = conn.execute("DELETE FROM measurements WHERE source IN ('live_hardware', 'simulated') "
                             "AND substr(received_at, 1, 10) >= ?", (today,)).rowcount
            j = conn.execute("DELETE FROM journal WHERE date >= ?", (today,)).rowcount
        app.logger.info("demo reset: removed %s readings and %s check-ins of %s", m, j, today)
        return jsonify({"status": "ok", "date": today, "removed_readings": m, "removed_checkins": j})

    @app.get("/api/export.csv")
    def export_csv():
        """CSV download for a spreadsheet. A missing value is an empty cell, never 0."""
        kind = request.args.get("kind", "measurements")
        if kind not in ("measurements", "journal"):
            raise ValidationError("kind must be measurements or journal", "kind")
        source, date, days = arg_source("simulated"), arg_date(), arg_int("days", 7, 1, 365)
        first = analysis.date_range(date, days)[0]
        out = io.StringIO()
        writer = csv.writer(out)
        with get_db(app.config["DB_PATH"]) as conn:
            if kind == "measurements":
                columns = ["id", "received_at", *COLUMNS]
                where, w_params = analysis.source_where(conn, source)
                rows = conn.execute(
                    f"SELECT {', '.join(columns)} FROM measurements WHERE {where} "
                    "AND substr(received_at, 1, 10) BETWEEN ? AND ? ORDER BY received_at, id LIMIT 50000",
                    (*w_params, first, date)).fetchall()
            else:
                columns = ["date", *JOURNAL_ANSWERS, "note", "received_at", "source"]
                j_where, j_params = analysis.journal_where(source)
                rows = conn.execute(
                    f"SELECT {', '.join(columns)} FROM journal WHERE {j_where} AND date BETWEEN ? AND ? "
                    "ORDER BY date", (*j_params, first, date)).fetchall()
        writer.writerow(columns)
        for row in rows:
            writer.writerow(["" if row[c] is None else csv_safe(row[c]) for c in columns])
        name = f"astra_{kind}_{source}_{date}.csv"
        return Response(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/reference")
    def get_reference():
        """Curated external references (literature and public datasets). Never mixed with measurements."""
        try:
            items = reference.load(reference_file)
        except (OSError, ValueError) as err:
            app.logger.error("could not load reference data: %s", err)
            return jsonify({"status": "error", "message": "reference data is not available"}), 500
        topic = request.args.get("topic")
        if topic is not None:
            if topic not in reference.TOPICS:
                raise ValidationError(f"topic must be one of {sorted(reference.TOPICS)}", "topic")
            items = [i for i in items if topic in i["topics"]]
        return jsonify({"count": len(items), "source": "external", "items": items})

    @app.get("/api/osdr/search")
    def osdr_search():
        """Search NASA OSDR study metadata (external, read only). Needs internet; fails cleanly without it."""
        try:
            size = int(request.args.get("size", "10"))
        except ValueError:
            raise ValidationError("size must be a whole number", "size")
        try:
            return jsonify(osdr.search(request.args.get("q", ""), request.args.get("type", "all"), size, osdr_fetch))
        except ValueError as err:
            raise ValidationError(str(err))
        except Exception as err:        # network down, timeout, unexpected answer
            app.logger.warning("OSDR search failed: %s: %s", type(err).__name__, err)
            return jsonify({"status": "error", "message": "NASA OSDR could not be reached. Try again later."}), 502

    @app.post("/api/journal")
    def post_journal():
        data = request.get_json(silent=True)
        if data is None:
            raise ValidationError("body must be valid JSON with Content-Type: application/json")
        clean = validate_journal(data)
        received_at = datetime.now().astimezone().isoformat(timespec="seconds")
        columns = ["date", "received_at", *JOURNAL_ANSWERS, "note"]
        values = [clean["date"], received_at, *(clean[c] for c in [*JOURNAL_ANSWERS, "note"])]
        # One entry per date: posting the same date again replaces the earlier answers.
        sql = (f"INSERT OR REPLACE INTO journal ({', '.join(columns)}) "
               f"VALUES ({', '.join('?' * len(columns))})")
        try:
            with get_db(app.config["DB_PATH"]) as conn:
                conn.execute(sql, values)
        except sqlite3.Error:
            app.logger.exception("could not save journal entry")
            return jsonify({"status": "error", "message": "could not save the journal entry"}), 500
        return jsonify({"status": "ok", "date": clean["date"], "received_at": received_at}), 201

    @app.get("/api/journal")
    def get_journal():
        date_arg = request.args.get("date")
        cols = ", ".join(["date", *JOURNAL_ANSWERS, "note", "received_at", "source"])
        if date_arg is not None:
            if not DATE_RE.match(date_arg):
                raise ValidationError("date must look like 2026-11-14", "date")
            with get_db(app.config["DB_PATH"]) as conn:
                row = conn.execute(f"SELECT {cols} FROM journal WHERE date = ?", (date_arg,)).fetchone()
            if row is None:
                return jsonify({"status": "error", "message": "no journal entry for that date"}), 404
            return jsonify(dict(row))
        try:
            limit = int(request.args.get("limit", "30"))
        except ValueError:
            raise ValidationError("limit must be a whole number", "limit")
        if limit < 1:
            raise ValidationError("limit must be at least 1", "limit")
        with get_db(app.config["DB_PATH"]) as conn:
            rows = conn.execute(f"SELECT {cols} FROM journal ORDER BY date DESC LIMIT ?",
                                (min(limit, 365),)).fetchall()
        items = [dict(r) for r in rows]
        return jsonify({"count": len(items), "items": items})

    # The dashboard: http://<LAPTOP_IP>:5000/ serves frontend/index.html, so the page and the
    # API share one address and the page can call the API with the relative path /api.
    @app.get("/")
    def dashboard():
        if not (frontend / "index.html").is_file():
            return jsonify({"status": "error", "message": "frontend/index.html not found yet"}), 404
        return send_from_directory(frontend, "index.html")

    @app.get("/<path:filename>")
    def frontend_file(filename):
        if filename.startswith("api/"):
            return handle_404(None)
        return send_from_directory(frontend, filename)

    return app


if __name__ == "__main__":
    # 0.0.0.0 makes the server reachable from the ESP32 over the local Wi-Fi.
    analysis.MEMO_BY_TIME_ONLY = True      # the live server reuses answers for a few seconds even when a reading just arrived
    create_app(log_path=BASE_DIR / "astra.log", noaa_background=True).run(host="0.0.0.0", port=5000, debug=False)

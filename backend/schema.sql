-- ASTRA sensor measurements (docs/api_contract.md section 5).
-- Every sensor column allows NULL: a missing value is NULL, never 0.
CREATE TABLE IF NOT EXISTS measurements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at    TEXT NOT NULL,   -- server time of receipt, ISO 8601 with time zone
    device_id      TEXT NOT NULL,
    heart_rate_bpm REAL,
    spo2_percent   REAL,
    accel_x_g      REAL,
    accel_y_g      REAL,
    accel_z_g      REAL,
    gyro_x_dps     REAL,
    gyro_y_dps     REAL,
    gyro_z_dps     REAL,
    signal_quality TEXT NOT NULL DEFAULT 'unknown',
    source         TEXT NOT NULL,
    uptime_ms      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_measurements_received_at ON measurements (received_at);

-- Daily self-reported check-in (docs/api_contract.md section 6.5). One row per date.
-- Kept apart from sensor data. Every answer allows NULL: a skipped question is NULL, never 0.
CREATE TABLE IF NOT EXISTS journal (
    date        TEXT PRIMARY KEY,   -- YYYY-MM-DD, the day the entry is about
    received_at TEXT NOT NULL,      -- server time of the last save
    sleep_hours REAL,
    mood        INTEGER,
    energy      INTEGER,
    stress      INTEGER,
    fatigue     INTEGER,
    note        TEXT,
    source      TEXT NOT NULL DEFAULT 'self_reported'  -- 'simulated' only for seeded demo entries
);

-- Radiation Risk Monitor (docs/RADIATION_MONITOR.md, contract 6.15). Kept apart from the sensor measurements.
-- Proton flux (>=10 MeV, pfu) from NOAA GOES (source 'external') or from the simulator ('simulated'). Times are UTC.
CREATE TABLE IF NOT EXISTS radiation_samples (
    source    TEXT NOT NULL,       -- 'external' (NOAA GOES) or 'simulated'
    time_tag  TEXT NOT NULL,       -- UTC, ISO 8601 with +00:00
    flux_pfu  REAL NOT NULL,       -- integral proton flux >=10 MeV, protons/(cm2 s sr)
    satellite INTEGER,
    PRIMARY KEY (source, time_tag)
);

-- Illustrative dose entries for the educational exposure budget. Never computed from flux.
CREATE TABLE IF NOT EXISTS radiation_dose (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source    TEXT NOT NULL,       -- the budget this entry belongs to ('external' or 'simulated')
    at        TEXT NOT NULL,       -- UTC
    msv       REAL NOT NULL,
    origin    TEXT NOT NULL,       -- 'simulated_event' or 'operator_entered'
    event_ref TEXT,
    note      TEXT
);

-- Acknowledged alerts (alert ids are deterministic, see radiation.py).
CREATE TABLE IF NOT EXISTS radiation_ack (
    alert_id        TEXT PRIMARY KEY,
    acknowledged_at TEXT NOT NULL
);

-- Small key/value store: NOAA fetch status and the budget settings of each source.
CREATE TABLE IF NOT EXISTS radiation_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);


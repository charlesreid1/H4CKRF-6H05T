-- schema_version 1
--
-- Applied on every startup. Statements are idempotent: CREATE TABLE IF NOT
-- EXISTS, CREATE INDEX IF NOT EXISTS. Any breaking change bumps the version
-- and lands as a new migration function in db.py (see _migrate_v1_to_v2, etc.).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT    NOT NULL,
    session_id      TEXT    NOT NULL,
    timestamp       REAL    NOT NULL,     -- Unix epoch seconds, UTC
    event           TEXT    NOT NULL,     -- AuditEventType value
    action          TEXT,                 -- CommandAction value, nullable
    risk_level      TEXT,                 -- RiskLevel value, nullable
    payload_json    TEXT,                 -- opaque JSON blob, caller-serialized
    blocked_reason  TEXT,
    duration_ms     INTEGER
);

CREATE INDEX IF NOT EXISTS audit_trace_idx   ON audit(trace_id);
CREATE INDEX IF NOT EXISTS audit_session_idx ON audit(session_id);
CREATE INDEX IF NOT EXISTS audit_ts_idx      ON audit(timestamp);

CREATE TABLE IF NOT EXISTS grants (
    id              TEXT    PRIMARY KEY,           -- UUID as string
    kind            TEXT    NOT NULL,              -- "tx" for now
    band_start_hz   INTEGER NOT NULL,
    band_stop_hz    INTEGER NOT NULL,
    max_gain_db     INTEGER NOT NULL,
    granted_at      REAL    NOT NULL,              -- Unix epoch seconds, UTC
    expires_at      REAL    NOT NULL,
    revoked_at      REAL,                          -- null iff not revoked
    CHECK (band_start_hz < band_stop_hz),
    CHECK (max_gain_db >= 0),
    CHECK (kind IN ('tx'))                          -- extend when RX grants land
);

CREATE INDEX IF NOT EXISTS grants_expires_idx ON grants(expires_at);
CREATE INDEX IF NOT EXISTS grants_kind_idx    ON grants(kind);

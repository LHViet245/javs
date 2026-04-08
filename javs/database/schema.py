"""SQLite schema and row helpers for the platform database."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

INITIAL_SCHEMA_VERSION = "0001_platform_foundation"
JOB_EVENTS_JOB_ITEM_MATCH_VERSION = "0002_job_events_match_job_items"

CREATE_SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

INITIAL_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        origin TEXT NOT NULL,
        request_json TEXT,
        result_json TEXT,
        summary_json TEXT,
        error_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        item_key TEXT NOT NULL,
        source_path TEXT,
        dest_path TEXT,
        movie_id TEXT,
        status TEXT NOT NULL,
        step TEXT,
        message TEXT,
        metadata_json TEXT,
        error_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_job_items_job_id
    ON job_items (job_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        job_item_id INTEGER REFERENCES job_items(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_job_events_job_id
    ON job_events (job_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS settings_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        source_path TEXT NOT NULL,
        config_version INTEGER NOT NULL,
        before_json TEXT,
        after_json TEXT,
        change_summary_json TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_settings_audit_job_id
    ON settings_audit (job_id)
    """,
)

MIGRATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (INITIAL_SCHEMA_VERSION, INITIAL_SCHEMA_STATEMENTS),
    (
        JOB_EVENTS_JOB_ITEM_MATCH_VERSION,
        (
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_items_job_id_id
            ON job_items (job_id, id)
            """,
            """
            CREATE TABLE job_events_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                job_item_id INTEGER,
                event_type TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id, job_item_id)
                    REFERENCES job_items(job_id, id)
                    ON DELETE CASCADE
            )
            """,
            """
            INSERT INTO job_events_v2 (
                id,
                job_id,
                job_item_id,
                event_type,
                payload_json,
                created_at
            )
            SELECT id, job_id, job_item_id, event_type, payload_json, created_at
            FROM job_events
            """,
            """
            DROP TABLE job_events
            """,
            """
            ALTER TABLE job_events_v2 RENAME TO job_events
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_job_events_job_id
            ON job_events (job_id)
            """,
        ),
    ),
)

JOB_JSON_FIELDS = ("request_json", "result_json", "summary_json", "error_json")
JOB_ITEM_JSON_FIELDS = ("metadata_json", "error_json")
JOB_EVENT_JSON_FIELDS = ("payload_json",)
SETTINGS_AUDIT_JSON_FIELDS = ("before_json", "after_json", "change_summary_json")


def dump_json(value: object | None) -> str | None:
    """Serialize JSON-compatible data for SQLite storage."""
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def load_json(value: str | None) -> Any:
    """Deserialize a JSON column from SQLite into Python data."""
    if value is None:
        return None
    return json.loads(value)


def row_to_dict(row: sqlite3.Row, *, json_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    """Convert a SQLite row to a plain dict, decoding selected JSON columns."""
    data = dict(row)
    for field in json_fields:
        if field in data:
            data[field] = load_json(data[field])
    return data

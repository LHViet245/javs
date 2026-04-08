"""Tests for the platform SQLite schema and repositories."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from javs.database.migrations import initialize_database
from javs.database.repositories.events import JobEventsRepository
from javs.database.repositories.job_items import JobItemsRepository
from javs.database.repositories.jobs import JobsRepository
from javs.database.repositories.settings_audit import SettingsAuditRepository


def connect_database(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection configured for mapping-style row access."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_table_names(path: Path) -> set[str]:
    """Return all non-SQLite internal table names from the database."""
    with connect_database(path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

    return {row["name"] for row in rows}


def test_initialize_platform_schema_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"

    initialize_database(db_path)

    names = fetch_table_names(db_path)

    assert {"jobs", "job_items", "job_events", "settings_audit", "schema_migrations"} <= names


def test_initialize_platform_schema_records_migration_version(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"

    initialize_database(db_path)

    with connect_database(db_path) as connection:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert [row["version"] for row in rows] == ["0001_platform_foundation"]


def test_job_repository_can_create_get_list_and_update_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with connect_database(db_path) as connection:
        repository = JobsRepository(connection)

        first_job_id = repository.create_job(
            kind="find",
            origin="cli",
            request_json={"movie_id": "ABP-420"},
        )
        second_job_id = repository.create_job(
            kind="sort",
            origin="api",
            request_json={"source": "/library/incoming"},
        )

        repository.mark_started(first_job_id)
        repository.mark_completed(
            first_job_id,
            result_json={"movie_id": "ABP-420"},
            summary_json={"matched": 1},
        )
        repository.update_job(second_job_id, status="failed", error_json={"message": "boom"})

        first_job = repository.get(first_job_id)
        all_jobs = repository.list_jobs()

    assert first_job is not None
    assert first_job["id"] == first_job_id
    assert first_job["kind"] == "find"
    assert first_job["status"] == "completed"
    assert first_job["origin"] == "cli"
    assert first_job["request_json"] == {"movie_id": "ABP-420"}
    assert first_job["result_json"] == {"movie_id": "ABP-420"}
    assert first_job["summary_json"] == {"matched": 1}
    assert first_job["started_at"] is not None
    assert first_job["finished_at"] is not None
    assert [job["id"] for job in all_jobs] == [second_job_id, first_job_id]
    assert all_jobs[0]["status"] == "failed"
    assert all_jobs[0]["error_json"] == {"message": "boom"}


def test_supporting_repositories_store_basic_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with connect_database(db_path) as connection:
        jobs = JobsRepository(connection)
        items = JobItemsRepository(connection)
        events = JobEventsRepository(connection)
        settings_audit = SettingsAuditRepository(connection)

        job_id = jobs.create_job(
            kind="sort",
            origin="cli",
            request_json={"source": "/library/incoming"},
        )
        job_item_id = items.create_item(
            job_id=job_id,
            item_key="item-1",
            source_path="/library/incoming/ABP-420.mp4",
            movie_id="ABP-420",
            status="pending",
            metadata_json={"index": 1},
        )
        event_id = events.add_event(
            job_id=job_id,
            job_item_id=job_item_id,
            event_type="item.created",
            payload_json={"item_key": "item-1"},
        )
        audit_id = settings_audit.create_entry(
            job_id=job_id,
            source_path="/tmp/config.yaml",
            config_version=1,
            before_json={"database": {"enabled": True}},
            after_json={"database": {"enabled": False}},
            change_summary_json={"changed": ["database.enabled"]},
        )

        stored_items = items.list_for_job(job_id)
        stored_events = events.list_for_job(job_id)
        stored_audits = settings_audit.list_entries()

    assert job_item_id > 0
    assert event_id > 0
    assert audit_id > 0
    assert stored_items == [
        {
            "id": job_item_id,
            "job_id": job_id,
            "item_key": "item-1",
            "source_path": "/library/incoming/ABP-420.mp4",
            "dest_path": None,
            "movie_id": "ABP-420",
            "status": "pending",
            "step": None,
            "message": None,
            "metadata_json": {"index": 1},
            "error_json": None,
            "started_at": None,
            "finished_at": None,
            "created_at": stored_items[0]["created_at"],
        }
    ]
    assert stored_events == [
        {
            "id": event_id,
            "job_id": job_id,
            "job_item_id": job_item_id,
            "event_type": "item.created",
            "payload_json": {"item_key": "item-1"},
            "created_at": stored_events[0]["created_at"],
        }
    ]
    assert stored_audits == [
        {
            "id": audit_id,
            "job_id": job_id,
            "source_path": "/tmp/config.yaml",
            "config_version": 1,
            "before_json": {"database": {"enabled": True}},
            "after_json": {"database": {"enabled": False}},
            "change_summary_json": {"changed": ["database.enabled"]},
            "created_at": stored_audits[0]["created_at"],
        }
    ]

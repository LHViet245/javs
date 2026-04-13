"""Tests for the platform SQLite schema and repositories."""

from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from javs.database.connection import open_database
from javs.database.migrations import apply_migrations, initialize_database
from javs.database.repositories.events import JobEventsRepository
from javs.database.repositories.job_items import JobItemsRepository
from javs.database.repositories.jobs import JobsRepository, _decode_cursor
from javs.database.repositories.settings_audit import SettingsAuditRepository
from javs.database.schema import (
    CREATE_SCHEMA_MIGRATIONS_TABLE_SQL,
    INITIAL_SCHEMA_STATEMENTS,
    INITIAL_SCHEMA_VERSION,
)


@dataclass(slots=True)
class JobListQuery:
    """Test-only stand-in for the history list query contract."""

    limit: int | None = None
    cursor: str | None = None
    kind: str | None = None
    status: str | None = None
    origin: str | None = None
    q: str | None = None


@dataclass(slots=True)
class HistoryContext:
    """Grouped repositories for cursor and detail history tests."""

    jobs: JobsRepository
    items: JobItemsRepository
    events: JobEventsRepository
    settings_audit: SettingsAuditRepository


def fetch_table_names(path: Path) -> set[str]:
    """Return all non-SQLite internal table names from the database."""
    with open_database(path) as connection:
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

    with open_database(db_path) as connection:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert [row["version"] for row in rows] == [
        "0001_platform_foundation",
        "0002_job_events_match_job_items",
    ]


def test_open_database_configures_mapping_rows_and_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"

    initialize_database(db_path)

    with open_database(db_path) as connection:
        pragma_row = connection.execute("PRAGMA foreign_keys").fetchone()
        table_row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name LIMIT 1"
        ).fetchone()

    assert pragma_row is not None
    assert pragma_row[0] == 1
    assert isinstance(table_row, sqlite3.Row)
    assert table_row["name"] is not None


def test_initialize_database_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"

    initialize_database(db_path)
    initialize_database(db_path)

    with open_database(db_path) as connection:
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()

    assert [row["version"] for row in rows] == [
        "0001_platform_foundation",
        "0002_job_events_match_job_items",
    ]


def test_job_repository_can_create_get_list_and_update_jobs(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with open_database(db_path) as connection:
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

    with open_database(db_path) as connection:
        repository = JobsRepository(connection)
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


def make_job_repo(tmp_path: Path) -> JobsRepository:
    """Return a jobs repository backed by a fresh platform database."""
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)
    connection = open_database(db_path)
    return JobsRepository(connection)


def make_history_context(tmp_path: Path) -> HistoryContext:
    """Return repositories backed by a fresh shared platform database."""
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)
    connection = open_database(db_path)
    return HistoryContext(
        jobs=JobsRepository(connection),
        items=JobItemsRepository(connection),
        events=JobEventsRepository(connection),
        settings_audit=SettingsAuditRepository(connection),
    )


def seed_job(
    repo: JobsRepository,
    *,
    kind: str,
    status: str = "pending",
    origin: str = "cli",
    created_at: str | None = None,
    job_id: str | None = None,
    request_json: object | None = None,
) -> str:
    """Insert a job row with optional deterministic ID and timestamp."""
    import uuid

    active_job_id = job_id or str(uuid.uuid4())
    if created_at is None:
        repo.connection.execute(
            """
            INSERT INTO jobs (id, kind, status, origin, request_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (active_job_id, kind, status, origin, request_json),
        )
    else:
        repo.connection.execute(
            """
            INSERT INTO jobs (id, kind, status, origin, request_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (active_job_id, kind, status, origin, request_json, created_at),
        )
    return active_job_id


def seed_job_with_item(
    context: HistoryContext,
    *,
    source_path: str | None = None,
    dest_path: str | None = None,
    movie_id: str | None = None,
    job_id: str | None = None,
) -> str:
    """Create a job with one persisted item for history search tests."""
    active_job_id = seed_job(context.jobs, kind="sort", status="completed", job_id=job_id)
    context.items.create_item(
        job_id=active_job_id,
        item_key="item-1",
        status="completed",
        source_path=source_path,
        dest_path=dest_path,
        movie_id=movie_id,
    )
    return active_job_id


def decode_cursor_payload(cursor: str) -> dict[str, Any]:
    """Decode a repository cursor into the JSON payload used in tests."""
    padded = cursor + "=" * (-len(cursor) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))


def encode_cursor_payload(payload: dict[str, Any]) -> str:
    """Encode a tampered cursor payload for negative-path tests."""
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def test_jobs_repository_lists_filtered_jobs_with_cursor(tmp_path: Path) -> None:
    repo = make_job_repo(tmp_path)
    seed_job(
        repo,
        kind="find",
        status="completed",
        origin="cli",
        created_at="2026-04-10T10:00:00Z",
    )
    second_id = seed_job(
        repo,
        kind="sort",
        status="running",
        origin="api",
        created_at="2026-04-10T10:00:01Z",
    )
    page = repo.list_jobs_page(JobListQuery(limit=1))
    assert [item["id"] for item in page.items] == [second_id]
    assert page.next_cursor is not None


def test_jobs_repository_cursor_is_stable_for_created_at_desc_id_desc_order(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    newest = seed_job(
        context.jobs,
        kind="sort",
        created_at="2026-04-10T10:00:00Z",
        job_id="job-b",
    )
    older_same_time = seed_job(
        context.jobs,
        kind="sort",
        created_at="2026-04-10T10:00:00Z",
        job_id="job-a",
    )
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1))
    second_page = context.jobs.list_jobs_page(JobListQuery(limit=1, cursor=first_page.next_cursor))
    assert [item["id"] for item in first_page.items] == [newest]
    assert [item["id"] for item in second_page.items] == [older_same_time]


@pytest.mark.parametrize(
    ("search_value", "item_kwargs", "duplicate_matching_item"),
    [
        ("job-search-001", {"job_id": "job-search-001"}, False),
        ("ABP-420", {"movie_id": "ABP-420"}, True),
        (
            "/library/incoming/ABP-420.mp4",
            {"source_path": "/library/incoming/ABP-420.mp4"},
            True,
        ),
        (
            "/library/sorted/ABP-420.mp4",
            {"dest_path": "/library/sorted/ABP-420.mp4"},
            True,
        ),
    ],
)
def test_jobs_repository_search_matches_job_and_item_fields(
    tmp_path: Path,
    search_value: str,
    item_kwargs: dict[str, str],
    duplicate_matching_item: bool,
) -> None:
    context = make_history_context(tmp_path)
    job_id = seed_job_with_item(
        context,
        job_id=item_kwargs.get("job_id", "job-search-001"),
        source_path=item_kwargs.get("source_path"),
        dest_path=item_kwargs.get("dest_path"),
        movie_id=item_kwargs.get("movie_id"),
    )
    if duplicate_matching_item:
        context.items.create_item(
            job_id=job_id,
            item_key="item-2",
            status="completed",
            source_path=item_kwargs.get("source_path"),
            dest_path=item_kwargs.get("dest_path"),
            movie_id=item_kwargs.get("movie_id"),
        )

    page = context.jobs.list_jobs_page(JobListQuery(q=search_value))

    assert [item["id"] for item in page.items] == [job_id]


def test_jobs_repository_search_treats_like_metacharacters_as_literals(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    percent_job_id = seed_job_with_item(
        context,
        job_id="job-percent",
        source_path="/incoming/100%.mkv",
        movie_id="100%",
    )
    underscore_job_id = seed_job_with_item(
        context,
        job_id="job-underscore",
        source_path="/incoming/ABC_123.mkv",
        movie_id="ABC_123",
    )

    percent_page = context.jobs.list_jobs_page(JobListQuery(q="%"))
    underscore_page = context.jobs.list_jobs_page(JobListQuery(q="_"))

    assert [item["id"] for item in percent_page.items] == [percent_job_id]
    assert [item["id"] for item in underscore_page.items] == [underscore_job_id]


def test_jobs_repository_filters_by_status_and_origin(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="find", status="completed", origin="cli")
    target = seed_job(context.jobs, kind="sort", status="running", origin="api")
    page = context.jobs.list_jobs_page(JobListQuery(status="running", origin="api"))
    assert [item["id"] for item in page.items] == [target]


def test_jobs_repository_rejects_cursor_when_query_envelope_changes(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1, status="running"))
    with pytest.raises(ValueError, match="cursor"):
        context.jobs.list_jobs_page(
            JobListQuery(limit=1, cursor=first_page.next_cursor, status="completed")
        )


def test_jobs_repository_rejects_cursor_when_anchor_row_does_not_exist(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1, status="running"))
    assert first_page.next_cursor is not None
    tampered_cursor = encode_cursor_payload(
        {
            **decode_cursor_payload(first_page.next_cursor),
            "id": "missing-job",
        }
    )

    with pytest.raises(ValueError, match="cursor anchor"):
        context.jobs.list_jobs_page(
            JobListQuery(limit=1, cursor=tampered_cursor, status="running")
        )


@pytest.mark.parametrize(
    ("mutate_payload", "match"),
    [
        (lambda payload: {**payload, "unexpected": "field"}, "cursor"),
        (
            lambda payload: {
                **payload,
                "query": {**payload["query"], "unexpected": "field"},
            },
            "cursor",
        ),
        (lambda payload: {**payload, "id": 123}, "cursor"),
    ],
)
def test_jobs_repository_rejects_tampered_cursor_payload_structure(
    tmp_path: Path,
    mutate_payload: Any,
    match: str,
) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1, status="running"))
    assert first_page.next_cursor is not None
    tampered_cursor = encode_cursor_payload(
        mutate_payload(decode_cursor_payload(first_page.next_cursor))
    )

    with pytest.raises(ValueError, match=match):
        _decode_cursor(tampered_cursor)


def test_jobs_repository_rejects_limit_greater_than_100(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)

    with pytest.raises(ValueError, match="limit"):
        context.jobs.list_jobs_page(JobListQuery(limit=101))


def test_supporting_repositories_store_basic_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with open_database(db_path) as connection:
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

    with open_database(db_path) as connection:
        items = JobItemsRepository(connection)
        events = JobEventsRepository(connection)
        settings_audit = SettingsAuditRepository(connection)
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


def test_job_events_repository_get_for_job_returns_newest_row_and_isolated_rows(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    first_job_id = seed_job(context.jobs, kind="sort", status="completed", job_id="job-a")
    second_job_id = seed_job(context.jobs, kind="sort", status="completed", job_id="job-b")
    context.events.add_event(
        job_id=first_job_id,
        event_type="item.created",
        payload_json={"step": 1},
    )
    newest_event_id = context.events.add_event(
        job_id=first_job_id,
        event_type="item.completed",
        payload_json={"step": 2},
    )
    cross_job_event_id = context.events.add_event(
        job_id=second_job_id,
        event_type="item.created",
        payload_json={"step": 3},
    )

    newest_event = context.events.get_for_job(first_job_id)
    second_event = context.events.get_for_job(second_job_id)

    assert newest_event is not None
    assert newest_event["id"] == newest_event_id
    assert newest_event["job_id"] == first_job_id
    assert newest_event["event_type"] == "item.completed"
    assert newest_event["payload_json"] == {"step": 2}
    assert context.events.get_for_job("missing-job") is None
    assert second_event is not None
    assert second_event["id"] == cross_job_event_id
    assert second_event["job_id"] == second_job_id
    assert second_event["event_type"] == "item.created"
    assert second_event["payload_json"] == {"step": 3}


def test_settings_audit_repository_get_for_job_returns_newest_row_and_isolated_rows(
    tmp_path: Path,
) -> None:
    context = make_history_context(tmp_path)
    first_job_id = seed_job(context.jobs, kind="sort", status="completed", job_id="job-a")
    second_job_id = seed_job(context.jobs, kind="sort", status="completed", job_id="job-b")
    context.settings_audit.create_entry(
        job_id=first_job_id,
        source_path="/tmp/older.yaml",
        config_version=1,
        before_json={"database": {"enabled": True}},
    )
    newest_audit_id = context.settings_audit.create_entry(
        job_id=first_job_id,
        source_path="/tmp/newest.yaml",
        config_version=2,
        before_json={"database": {"enabled": False}},
        after_json={"database": {"enabled": True}},
    )
    cross_job_audit_id = context.settings_audit.create_entry(
        job_id=second_job_id,
        source_path="/tmp/other.yaml",
        config_version=1,
        change_summary_json={"changed": ["proxy.enabled"]},
    )

    newest_audit = context.settings_audit.get_for_job(first_job_id)
    second_audit = context.settings_audit.get_for_job(second_job_id)

    assert newest_audit is not None
    assert newest_audit["id"] == newest_audit_id
    assert newest_audit["job_id"] == first_job_id
    assert newest_audit["source_path"] == "/tmp/newest.yaml"
    assert newest_audit["config_version"] == 2
    assert newest_audit["before_json"] == {"database": {"enabled": False}}
    assert newest_audit["after_json"] == {"database": {"enabled": True}}
    assert context.settings_audit.get_for_job("missing-job") is None
    assert second_audit is not None
    assert second_audit["id"] == cross_job_audit_id
    assert second_audit["job_id"] == second_job_id
    assert second_audit["source_path"] == "/tmp/other.yaml"
    assert second_audit["config_version"] == 1
    assert second_audit["before_json"] is None
    assert second_audit["after_json"] is None
    assert second_audit["change_summary_json"] == {"changed": ["proxy.enabled"]}


def test_job_items_enforce_parent_job_foreign_key(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with open_database(db_path) as connection:
        items = JobItemsRepository(connection)

        try:
            items.create_item(
                job_id="missing-job",
                item_key="item-1",
                status="pending",
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected foreign key enforcement for job_items.job_id")


def test_job_events_reject_job_items_from_a_different_job(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with open_database(db_path) as connection:
        jobs = JobsRepository(connection)
        items = JobItemsRepository(connection)
        events = JobEventsRepository(connection)

        first_job_id = jobs.create_job(
            kind="sort",
            origin="cli",
            request_json={"source": "/library/a"},
        )
        second_job_id = jobs.create_job(
            kind="sort",
            origin="cli",
            request_json={"source": "/library/b"},
        )
        first_job_item_id = items.create_item(
            job_id=first_job_id,
            item_key="item-1",
            status="pending",
        )

        try:
            events.add_event(
                job_id=second_job_id,
                job_item_id=first_job_item_id,
                event_type="item.created",
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("expected job_events to reject cross-job job_item_id references")


def test_apply_migrations_repairs_legacy_cross_job_event_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-platform.db"

    with open_database(db_path) as connection:
        connection.execute(CREATE_SCHEMA_MIGRATIONS_TABLE_SQL)
        for statement in INITIAL_SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (INITIAL_SCHEMA_VERSION,),
        )
        connection.execute(
            """
            INSERT INTO jobs (id, kind, status, origin)
            VALUES ('job-a', 'sort', 'pending', 'cli')
            """
        )
        connection.execute(
            """
            INSERT INTO jobs (id, kind, status, origin)
            VALUES ('job-b', 'sort', 'pending', 'cli')
            """
        )
        connection.execute(
            """
            INSERT INTO job_items (job_id, item_key, status)
            VALUES ('job-a', 'item-1', 'pending')
            """
        )
        connection.execute(
            """
            INSERT INTO job_events (job_id, job_item_id, event_type)
            VALUES ('job-b', 1, 'item.created')
            """
        )

    with open_database(db_path) as connection:
        apply_migrations(connection)
        migrated_versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        migrated_event = connection.execute(
            "SELECT job_id, job_item_id, event_type FROM job_events"
        ).fetchone()

    assert [row["version"] for row in migrated_versions] == [
        "0001_platform_foundation",
        "0002_job_events_match_job_items",
    ]
    assert migrated_event is not None
    assert dict(migrated_event) == {
        "job_id": "job-b",
        "job_item_id": None,
        "event_type": "item.created",
    }


def test_deleting_a_job_cascades_to_child_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    with open_database(db_path) as connection:
        jobs = JobsRepository(connection)
        items = JobItemsRepository(connection)
        events = JobEventsRepository(connection)
        settings_audit = SettingsAuditRepository(connection)

        job_id = jobs.create_job(
            kind="sort",
            origin="cli",
            request_json={"source": "/library/incoming"},
        )
        job_item_id = items.create_item(job_id=job_id, item_key="item-1", status="pending")
        events.add_event(job_id=job_id, job_item_id=job_item_id, event_type="item.created")
        settings_audit.create_entry(
            job_id=job_id,
            source_path="/tmp/config.yaml",
            config_version=1,
        )
        connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    with open_database(db_path) as connection:
        counts = {
            "jobs": connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "job_items": connection.execute("SELECT COUNT(*) FROM job_items").fetchone()[0],
            "job_events": connection.execute("SELECT COUNT(*) FROM job_events").fetchone()[0],
            "settings_audit": connection.execute("SELECT COUNT(*) FROM settings_audit").fetchone()[
                0
            ],
        }

    assert counts == {
        "jobs": 0,
        "job_items": 0,
        "job_events": 0,
        "settings_audit": 0,
    }


def test_repository_writes_follow_connection_transaction_boundaries(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)

    connection = open_database(db_path)
    repository = JobsRepository(connection)
    job_id = repository.create_job(
        kind="find",
        origin="cli",
        request_json={"movie_id": "ABP-420"},
    )
    connection.rollback()
    connection.close()

    with open_database(db_path) as verify_connection:
        repository = JobsRepository(verify_connection)
        persisted_job = repository.get(job_id)

    assert persisted_job is None

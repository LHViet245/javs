"""Test configuration for pytest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(slots=True)
class PlatformRuntime:
    db_path: Path
    connection: object
    hub: object
    jobs: object
    events: object
    runner: object


@pytest.fixture
def sample_config():
    """Create a sample JavsConfig for testing."""
    from javs.config.models import JavsConfig

    return JavsConfig()


@pytest.fixture
def sample_movie_data():
    """Create sample MovieData for testing."""
    from datetime import date

    from javs.models.movie import Actress, MovieData, Rating

    return MovieData(
        id="ABP-420",
        title="Test Movie Title",
        alternate_title="テスト映画タイトル",
        description="A test movie description",
        rating=Rating(rating=7.5, votes=100),
        release_date=date(2023, 6, 15),
        runtime=120,
        director="Test Director",
        maker="Test Studio",
        label="Test Label",
        series="Test Series",
        genres=["Drama", "Romance"],
        actresses=[
            Actress(
                last_name="Suzuki",
                first_name="Koharu",
                japanese_name="鈴木心春",
            ),
        ],
        cover_url="https://example.com/cover.jpg",
        source="test",
    )


@pytest.fixture
def realtime_event_hub():
    from javs.jobs.events import EventHub

    return EventHub()


@pytest.fixture
def platform_runtime(tmp_path: Path, realtime_event_hub):
    from javs.database.connection import open_database
    from javs.database.migrations import initialize_database
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.jobs import PlatformJobRunner

    db_path = tmp_path / "platform.db"
    initialize_database(db_path)
    connection = open_database(db_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)

    runtime = PlatformRuntime(
        db_path=db_path,
        connection=connection,
        hub=realtime_event_hub,
        jobs=jobs,
        events=events,
        runner=PlatformJobRunner(jobs=jobs, events=events, hub=realtime_event_hub),
    )
    try:
        yield runtime
    finally:
        connection.close()

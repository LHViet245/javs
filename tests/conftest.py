"""Test configuration for pytest."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
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
def publish_test_event():
    from javs.jobs.events import RealtimeEvent

    def _publish(
        hub,
        *,
        event_id: int = 1,
        job_id: str = "job-1",
        event_type: str = "job.started",
        job_item_id: int | None = None,
        payload: object | None = None,
    ) -> RealtimeEvent:
        event = RealtimeEvent(
            id=event_id,
            job_id=job_id,
            event_type=event_type,
            job_item_id=job_item_id,
            payload=payload,
        )
        hub.publish_nowait(event)
        return event

    return _publish


@pytest.fixture
def websocket_session():
    @asynccontextmanager
    async def _session(app, path: str, *, query_string: bytes = b""):
        messages: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        receive_messages: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        connect_sent = False

        async def receive() -> dict[str, object]:
            nonlocal connect_sent
            if not connect_sent:
                connect_sent = True
                return {"type": "websocket.connect"}
            return await receive_messages.get()

        async def send(message: dict[str, object]) -> None:
            await messages.put(message)

        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query_string,
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "subprotocols": [],
        }
        task = asyncio.create_task(app(scope, receive, send))
        first_message = await asyncio.wait_for(messages.get(), timeout=1)
        if first_message["type"] != "websocket.accept":
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            raise AssertionError(f"Expected websocket.accept, got {first_message!r}")

        session = _ASGIWebSocketSession(
            task=task,
            messages=messages,
            receive_messages=receive_messages,
        )
        try:
            yield session
        finally:
            await session.aclose()

    return _session


class _ASGIWebSocketSession:
    def __init__(
        self,
        *,
        task: asyncio.Task[None],
        messages: asyncio.Queue[dict[str, object]],
        receive_messages: asyncio.Queue[dict[str, object]],
    ) -> None:
        self.task = task
        self._messages = messages
        self._receive_messages = receive_messages

    async def send_json(self, payload: object) -> None:
        await self._receive_messages.put(
            {"type": "websocket.receive", "text": json.dumps(payload, ensure_ascii=False)}
        )

    async def receive_json(self) -> dict[str, object]:
        while True:
            message = await asyncio.wait_for(self._messages.get(), timeout=1)
            if message["type"] == "websocket.send":
                text = message.get("text")
                if text is not None:
                    return json.loads(text)
                body = message.get("bytes")
                if body is not None:
                    return json.loads(body.decode("utf-8"))
            raise AssertionError(f"Unexpected websocket message: {message!r}")

    async def aclose(self) -> None:
        if not self.task.done():
            await self._receive_messages.put({"type": "websocket.disconnect"})
            try:
                await asyncio.wait_for(self.task, timeout=1)
            except TimeoutError:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass


@pytest.fixture
def api_app_with_hub(api_app, realtime_event_hub):
    return api_app[0], api_app[1], realtime_event_hub


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

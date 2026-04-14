"""Minimal ASGI app exposing the shared platform facade over HTTP."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs

from javs.api.routes.jobs import (
    build_realtime_event,
    handle_find_job,
    handle_get_job,
    handle_list_jobs,
    handle_sort_job,
    handle_update_job,
    serialize_realtime_event,
)
from javs.api.routes.settings import handle_get_settings, handle_save_settings
from javs.application import BatchJobError, SettingsSaveError
from javs.application.find import FindMovieError
from javs.application.settings import SettingsValidationError

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

_JOB_POST_PATHS = {"/jobs/find", "/jobs/sort", "/jobs/update", "/settings"}
_SSE_HEADERS = [
    (b"content-type", b"text/event-stream; charset=utf-8"),
    (b"cache-control", b"no-cache"),
    (b"connection", b"keep-alive"),
    (b"x-accel-buffering", b"no"),
]
_SSE_DISCONNECT_MESSAGE = {"type": "http.disconnect"}


@dataclass(slots=True)
class JavsAPIApp:
    """Very small ASGI adapter around the shared platform facade."""

    facade: object

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return

        if scope["type"] != "http":
            await self._send_json(send, 500, {"detail": "Unsupported ASGI scope type."})
            return

        method = scope["method"].upper()
        path = scope["path"]

        try:
            if method == "GET":
                if path == "/jobs":
                    payload = handle_list_jobs(self.facade, self._query_params(scope))
                    await self._send_json(send, 200, self._to_json_payload(payload))
                    return

                if path.startswith("/jobs/"):
                    job_id = path.removeprefix("/jobs/")
                    if not job_id or "/" in job_id:
                        await self._send_json(send, 404, {"detail": "Not found."})
                        return
                    payload = handle_get_job(self.facade, job_id)
                    if payload is None:
                        await self._send_json(send, 404, {"detail": "Not found."})
                        return
                    await self._send_json(send, 200, self._to_json_payload(payload))
                    return

                if path == "/settings":
                    source_path = self._query_param(scope, "source_path")
                    try:
                        payload = handle_get_settings(self.facade, source_path)
                    except Exception as error:
                        await self._send_json(send, 500, {"detail": str(error)})
                        return
                    await self._send_json(send, 200, self._to_json_payload(payload))
                    return

                if path == "/events/stream":
                    await self._stream_events(scope, receive, send)
                    return

            if method == "POST" and path in _JOB_POST_PATHS:
                body = await self._read_json_body(receive)
                if path == "/jobs/find":
                    payload = await handle_find_job(self.facade, body)
                elif path == "/jobs/sort":
                    payload = await handle_sort_job(self.facade, body)
                elif path == "/jobs/update":
                    payload = await handle_update_job(self.facade, body)
                else:
                    payload = await handle_save_settings(self.facade, body)
                await self._send_json(send, 200, self._to_json_payload(payload))
                return
        except ValueError as error:
            await self._send_json(send, 400, {"detail": str(error)})
            return
        except (
            FindMovieError,
            BatchJobError,
            SettingsSaveError,
            SettingsValidationError,
        ) as error:
            await self._send_json(send, 409, self._build_application_error_payload(error))
            return

        await self._send_json(send, 404, {"detail": "Not found."})

    async def _handle_lifespan(self, receive: Receive, send: Send) -> None:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
            while True:
                message = await receive()
                if message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        await send({"type": "lifespan.startup.failed", "message": "Unsupported lifespan event."})

    @staticmethod
    async def _read_json_body(receive: Receive) -> dict[str, Any]:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break
        raw = b"".join(chunks).strip()
        if not raw:
            return {}
        body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object.")
        return body

    @staticmethod
    async def _send_json(send: Send, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def _stream_events(self, scope: Scope, receive: Receive, send: Send) -> None:
        hub = self._event_hub()
        if hub is None:
            await self._send_json(send, 503, {"detail": "Realtime stream is unavailable."})
            return

        queue = hub.subscribe()
        job_id = self._query_param(scope, "job_id")

        try:
            await send({"type": "http.response.start", "status": 200, "headers": _SSE_HEADERS})
            await send({"type": "http.response.body", "body": b"", "more_body": True})
            while True:
                event = await queue.get()
                if job_id is not None and event.job_id != job_id:
                    continue

                shared_event = build_realtime_event(event)
                frame = serialize_realtime_event(shared_event)
                body = f"event: {shared_event.type}\ndata: {frame}\n\n".encode()
                await send({"type": "http.response.body", "body": body, "more_body": True})
        except asyncio.CancelledError:
            raise
        finally:
            hub.close(queue)

    @staticmethod
    def _to_json_payload(payload: Any) -> Any:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        return payload

    @staticmethod
    def _query_param(scope: Scope, name: str) -> str | None:
        query_string = scope.get("query_string", b"").decode("utf-8")
        query = parse_qs(query_string, keep_blank_values=True)
        values = query.get(name)
        if not values:
            return None
        return values[0] or None

    @staticmethod
    def _query_params(scope: Scope) -> dict[str, str]:
        query_string = scope.get("query_string", b"").decode("utf-8")
        query = parse_qs(query_string, keep_blank_values=True)
        return {key: values[0] for key, values in query.items() if values}

    def _event_hub(self) -> object | None:
        runner = getattr(self.facade, "runner", None)
        return getattr(runner, "hub", None)

    @staticmethod
    def _build_application_error_payload(
        error: FindMovieError
        | BatchJobError
        | SettingsSaveError
        | SettingsValidationError,
    ) -> dict[str, Any]:
        if isinstance(error, SettingsValidationError):
            return {
                "detail": str(error),
                "job_id": None,
                "error": {
                    "type": "SettingsValidationError",
                    "message": str(error),
                },
            }
        return {
            "detail": str(error),
            "job_id": error.job_id,
            "error": dict(error.error),
        }


def create_app(facade: object) -> JavsAPIApp:
    """Create the minimal ASGI application used by tests and future adapters."""
    return JavsAPIApp(facade=facade)

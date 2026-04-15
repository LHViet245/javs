"""Thin realtime route helpers for WebSocket job streams."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from javs.api.routes.jobs import build_realtime_event, serialize_realtime_event


@dataclass(slots=True, frozen=True)
class RealtimeSubscription:
    """Validated websocket subscription request."""

    job_id: str | None


async def handle_websocket_job_stream(facade, receive, send) -> None:
    """Subscribe the websocket client to the shared realtime hub."""
    hub = _event_hub(facade)
    if hub is None:
        await send(
            {
                "type": "websocket.close",
                "code": 1011,
                "reason": "Realtime stream is unavailable.",
            }
        )
        return

    message = await receive()
    if message["type"] != "websocket.connect":
        await send({"type": "websocket.close", "code": 1002})
        return

    await send({"type": "websocket.accept"})

    subscription = await _receive_subscription(receive)
    if subscription is None:
        await send({"type": "websocket.close", "code": 1003})
        return

    queue: Any | None = hub.subscribe()
    event_task: asyncio.Task[Any] | None = None
    disconnect_task: asyncio.Task[Any] | None = None
    try:
        await _send_json(
            send,
            {
                "type": "subscribed",
                "job_id": subscription.job_id,
            },
        )

        while True:
            event_task = asyncio.create_task(queue.get())
            disconnect_task = asyncio.create_task(receive())
            done, _pending = await asyncio.wait(
                {event_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if disconnect_task in done:
                message = disconnect_task.result()
                event_task.cancel()
                with suppress(asyncio.CancelledError):
                    await event_task
                if message["type"] == "websocket.disconnect":
                    break
                continue

            event = event_task.result()
            disconnect_task.cancel()
            with suppress(asyncio.CancelledError):
                await disconnect_task
            if subscription.job_id is not None and event.job_id != subscription.job_id:
                continue

            shared_event = build_realtime_event(event)
            await _send_json(send, json.loads(serialize_realtime_event(shared_event)))
    finally:
        if event_task is not None and not event_task.done():
            event_task.cancel()
        if disconnect_task is not None and not disconnect_task.done():
            disconnect_task.cancel()
        for task in (event_task, disconnect_task):
            if task is None:
                continue
            with suppress(asyncio.CancelledError):
                await task
        if queue is not None:
            hub.close(queue)


async def _receive_subscription(receive) -> RealtimeSubscription | None:
    while True:
        message = await receive()
        if message["type"] == "websocket.disconnect":
            return None
        if message["type"] != "websocket.receive":
            continue

        raw_text = message.get("text")
        raw_bytes = message.get("bytes")
        raw_value = raw_text if raw_text is not None else raw_bytes
        if raw_value is None:
            return None
        try:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            payload = json.loads(raw_value)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("action") != "subscribe":
            return None

        job_id = payload.get("job_id")
        if job_id in (None, ""):
            return RealtimeSubscription(job_id=None)
        if not isinstance(job_id, str):
            return None
        return RealtimeSubscription(job_id=job_id)


async def _send_json(send, payload: dict[str, Any]) -> None:
    await send({"type": "websocket.send", "text": json.dumps(payload, ensure_ascii=False)})


def _event_hub(facade) -> object | None:
    runner = getattr(facade, "runner", None)
    return getattr(runner, "hub", None)

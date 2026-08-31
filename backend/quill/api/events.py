"""SSE event hub (U-07). No client polling — drafts, sends, alerts pushed."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

_subscribers: set[asyncio.Queue] = set()


def publish(event: str, data: dict) -> None:
    payload = {"event": event, "data": data}
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


async def subscribe() -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)
    try:
        # initial hello so the connection opens immediately
        yield _format("hello", {"ok": True})
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=20)
                yield _format(item["event"], item["data"])
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subscribers.discard(q)


def _format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

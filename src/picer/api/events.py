"""Thread-safe event bus that bridges camera daemon threads to asyncio WebSocket handlers."""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import Any, Optional


class SequenceEventBus:
    """Publishes events from any thread; subscribers receive them via asyncio queues."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: set[asyncio.Queue] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    def publish(self, event: dict[str, Any]) -> None:
        """Thread-safe. Delivers event to all active WebSocket subscribers."""
        with self._lock:
            if self._loop is None:
                return
            for q in list(self._subscribers):
                self._loop.call_soon_threadsafe(q.put_nowait, event)

    @asynccontextmanager
    async def subscribe(self):
        """Async context manager yielding a queue that receives published events."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.add(q)
        try:
            yield q
        finally:
            with self._lock:
                self._subscribers.discard(q)

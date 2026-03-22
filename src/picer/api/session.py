"""Single-session lock with 30-minute idle timeout."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

SESSION_TIMEOUT = 30 * 60  # seconds


class SessionManager:
    """Allows only one client session at a time.

    The idle timer is paused while a sequence is running so long exposures
    don't cause an unwanted disconnect.
    """

    def __init__(self, on_timeout: Optional[Callable[[], None]] = None) -> None:
        self._lock = threading.Lock()
        self._held = False
        self._sequence_running = False
        self._timer: Optional[threading.Timer] = None
        self._on_timeout_cb = on_timeout

    def acquire(self) -> bool:
        """Try to acquire the session. Returns True if successful."""
        with self._lock:
            if self._held:
                return False
            self._held = True
            self._reset_timer()
            return True

    def release(self) -> None:
        with self._lock:
            self._cancel_timer()
            self._held = False
            self._sequence_running = False

    def is_held(self) -> bool:
        with self._lock:
            return self._held

    def touch(self) -> None:
        """Reset the idle timer (call on each authenticated request)."""
        with self._lock:
            if self._held and not self._sequence_running:
                self._reset_timer()

    def set_sequence_running(self, running: bool) -> None:
        with self._lock:
            self._sequence_running = running
            if running:
                self._cancel_timer()
            elif self._held:
                self._reset_timer()

    # ------------------------------------------------------------------

    def _reset_timer(self) -> None:
        self._cancel_timer()
        t = threading.Timer(SESSION_TIMEOUT, self._expire)
        t.daemon = True
        t.start()
        self._timer = t

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _expire(self) -> None:
        with self._lock:
            self._held = False
            self._sequence_running = False
            self._timer = None
        if self._on_timeout_cb:
            self._on_timeout_cb()

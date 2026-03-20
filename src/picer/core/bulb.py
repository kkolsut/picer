"""BulbExposure helper — used by SequenceRunner to track a single bulb exposure."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from picer.camera.models import BulbProgress


@dataclass
class BulbExposure:
    """
    Tracks progress for a bulb exposure running in a background thread.

    The caller is responsible for actually driving the camera (via the backend).
    This class only provides cancel signalling and a progress loop that can be
    run in the same background thread alongside the camera call.
    """

    duration_s: float
    on_progress: Optional[Callable[[BulbProgress], None]] = None
    _cancel: threading.Event = field(default_factory=threading.Event, init=False)
    _start_time: float = field(default=0.0, init=False)

    def start(self) -> None:
        self._start_time = time.monotonic()

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def run_progress_loop(self, poll_interval: float = 0.5) -> None:
        """Block until duration elapsed or cancelled, firing progress callbacks."""
        self._start_time = time.monotonic()
        while True:
            elapsed = time.monotonic() - self._start_time
            if self._cancel.is_set() or elapsed >= self.duration_s:
                break
            if self.on_progress is not None:
                self.on_progress(
                    BulbProgress(elapsed_s=elapsed, total_s=self.duration_s)
                )
            remaining = self.duration_s - elapsed
            time.sleep(min(poll_interval, remaining))

        # Final callback at 100 %
        if self.on_progress is not None and not self._cancel.is_set():
            self.on_progress(
                BulbProgress(elapsed_s=self.duration_s, total_s=self.duration_s)
            )

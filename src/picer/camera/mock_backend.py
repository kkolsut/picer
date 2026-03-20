"""Offline mock backend for development and testing without a physical camera."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from picer.camera.models import (
    BulbProgress,
    CameraConfig,
    CaptureResult,
    ShutterSpeed,
)


class MockBackend:
    """Simulates camera captures by writing empty placeholder files."""

    def __init__(self, sim_speed: float = 1.0) -> None:
        """
        sim_speed: time multiplier. 0.0 = instant, 1.0 = real time.
        Use a small value (e.g. 0.01) in tests to avoid waiting.
        """
        self._connected = False
        self._config = CameraConfig()
        self._sim_speed = sim_speed
        self._model = "Canon EOS 450D (mock)"

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def list_cameras(self) -> list[str]:
        return [f"{self._model} at usb:001,001"]

    def get_config(self) -> CameraConfig:
        return CameraConfig(
            shutter_speed=self._config.shutter_speed,
            iso=self._config.iso,
            capture_format=self._config.capture_format,
            bulb_duration_s=self._config.bulb_duration_s,
        )

    def apply_config(self, config: CameraConfig) -> None:
        self._config = config

    def capture_single(
        self,
        config: CameraConfig,
        dest: Path,
        index: int = 0,
        on_progress: Optional[Callable[[BulbProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> CaptureResult:
        dest.mkdir(parents=True, exist_ok=True)
        self.apply_config(config)
        t_start = time.time()

        duration = config.effective_exposure_s
        if duration == float("inf"):
            duration = config.bulb_duration_s

        # Simulate exposure time (scaled)
        sim_duration = duration * self._sim_speed
        interval = 0.1
        elapsed = 0.0
        while elapsed < sim_duration:
            if cancel_check is not None and cancel_check():
                break
            sleep_time = min(interval, sim_duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
            if on_progress is not None and config.shutter_speed == ShutterSpeed.BULB:
                real_elapsed = elapsed / max(self._sim_speed, 1e-9)
                on_progress(BulbProgress(elapsed_s=real_elapsed, total_s=duration))

        # Write a placeholder file
        ext = config.capture_format.extension
        filename = f"mock_{index:04d}{ext}"
        out_path = dest / filename
        out_path.write_bytes(b"MOCK_CR2_PLACEHOLDER")

        return CaptureResult(
            frame_index=index,
            file_path=out_path,
            exposure_s=duration,
            iso=config.iso,
            timestamp=t_start,
        )

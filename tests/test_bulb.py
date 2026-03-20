"""Tests for bulb exposure logic."""
from __future__ import annotations

from pathlib import Path

import pytest

from picer.camera.mock_backend import MockBackend
from picer.camera.models import BulbProgress, CameraConfig, ShutterSpeed


def test_bulb_capture_creates_file(tmp_output: Path, bulb_config: CameraConfig) -> None:
    backend = MockBackend(sim_speed=0.0)
    backend.connect()
    result = backend.capture_single(bulb_config, tmp_output)
    assert result.file_path.exists()
    assert result.file_path.suffix == ".cr2"


def test_bulb_progress_callbacks(tmp_output: Path) -> None:
    config = CameraConfig(
        shutter_speed=ShutterSpeed.BULB,
        bulb_duration_s=5.0,
    )
    backend = MockBackend(sim_speed=0.5)  # runs at 50% speed so progress fires

    progress_calls: list[BulbProgress] = []

    def on_progress(p: BulbProgress) -> None:
        progress_calls.append(p)

    backend.connect()
    result = backend.capture_single(config, tmp_output, on_progress=on_progress)

    assert result.exposure_s == 5.0
    # At least one progress callback fired
    assert len(progress_calls) > 0
    # Progress values should be within range
    for p in progress_calls:
        assert 0.0 <= p.percent <= 100.0


def test_bulb_cancel(tmp_output: Path) -> None:
    import threading

    config = CameraConfig(
        shutter_speed=ShutterSpeed.BULB,
        bulb_duration_s=60.0,
    )
    backend = MockBackend(sim_speed=1.0)
    backend.connect()

    cancelled = threading.Event()
    cancelled.set()  # immediately cancelled

    result = backend.capture_single(
        config, tmp_output, cancel_check=cancelled.is_set
    )
    # File should still be created (cancel just stops the wait loop early)
    assert result.file_path.exists()


def test_normal_capture_no_progress(tmp_output: Path, raw_config: CameraConfig) -> None:
    backend = MockBackend(sim_speed=0.0)
    backend.connect()

    calls: list[BulbProgress] = []
    result = backend.capture_single(raw_config, tmp_output, on_progress=calls.append)

    assert result.file_path.exists()
    # No progress callbacks for non-bulb captures
    assert len(calls) == 0

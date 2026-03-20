"""Tests for SequenceRunner."""
from __future__ import annotations

from pathlib import Path

import pytest

from picer.camera.models import CameraConfig, CaptureResult, SequenceConfig, ShutterSpeed
from picer.core.sequence import SequenceRunner


def test_sequence_captures_all_frames(
    mock_backend, tmp_output: Path, raw_config: CameraConfig
) -> None:
    seq_config = SequenceConfig(
        frame_count=3,
        interval_s=0.0,
        output_dir=tmp_output,
        filename_template="test_{seq:04d}",
        camera_config=raw_config,
    )
    runner = SequenceRunner(backend=mock_backend, config=seq_config)
    results = runner.run_blocking()

    assert len(results) == 3
    for i, r in enumerate(results):
        assert r.frame_index == i
        assert r.file_path.exists()


def test_sequence_frame_callbacks(mock_backend, tmp_output: Path, raw_config: CameraConfig) -> None:
    started: list[tuple[int, int]] = []
    completed: list[CaptureResult] = []

    seq_config = SequenceConfig(
        frame_count=2,
        output_dir=tmp_output,
        camera_config=raw_config,
    )
    runner = SequenceRunner(
        backend=mock_backend,
        config=seq_config,
        on_frame_start=lambda idx, total: started.append((idx, total)),
        on_frame_complete=lambda r: completed.append(r),
    )
    runner.run_blocking()

    assert started == [(0, 2), (1, 2)]
    assert len(completed) == 2


def test_sequence_cancel(mock_backend, tmp_output: Path) -> None:
    import threading
    import time

    config = CameraConfig(shutter_speed=ShutterSpeed.S_30)
    seq_config = SequenceConfig(
        frame_count=10,
        output_dir=tmp_output,
        camera_config=config,
    )
    runner = SequenceRunner(backend=mock_backend, config=seq_config)
    runner.start()

    time.sleep(0.05)
    runner.cancel()

    # Wait for thread to finish
    runner._thread.join(timeout=5)
    assert not runner.is_running()


def test_sequence_continues_on_error(mock_backend, tmp_output: Path) -> None:
    """on_error returning True should continue the sequence."""
    call_count = 0
    original_capture = mock_backend.capture_single

    def failing_capture(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated error on frame 1")
        return original_capture(*args, **kwargs)

    mock_backend.capture_single = failing_capture

    errors: list[tuple[int, Exception]] = []
    seq_config = SequenceConfig(
        frame_count=3,
        output_dir=tmp_output,
        camera_config=CameraConfig(),
    )
    runner = SequenceRunner(
        backend=mock_backend,
        config=seq_config,
        on_error=lambda idx, exc: (errors.append((idx, exc)), True)[-1],
    )
    results = runner.run_blocking()

    assert len(errors) == 1
    assert errors[0][0] == 0
    assert len(results) == 2  # frames 2 and 3 succeeded

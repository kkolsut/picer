"""Tests for filename template engine."""
from __future__ import annotations

from datetime import datetime

import pytest

from picer.camera.models import CameraConfig, CaptureFormat, ShutterSpeed
from picer.utils.file_naming import preview_filename, render_filename


@pytest.fixture
def config() -> CameraConfig:
    return CameraConfig(
        shutter_speed=ShutterSpeed.S_1,
        iso=400,
        capture_format=CaptureFormat.RAW,
    )


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 3, 15, 23, 59, 30)


def test_date_token(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{date}", config, seq=1, now=fixed_now)
    assert result == "2026-03-15"


def test_time_token(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{time}", config, seq=1, now=fixed_now)
    assert result == "235930"


def test_seq_zero_padded(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{seq:04d}", config, seq=7, now=fixed_now)
    assert result == "0007"


def test_combined_template(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("picer_{date}_{seq:04d}", config, seq=42, now=fixed_now)
    assert result == "picer_2026-03-15_0042"


def test_iso_token(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{iso}", config, seq=1, now=fixed_now)
    assert result == "400"


def test_exp_token(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{exp}", config, seq=1, now=fixed_now)
    assert "1" in result  # 1s exposure


def test_unknown_token_preserved(config: CameraConfig, fixed_now: datetime) -> None:
    result = render_filename("{unknown}", config, seq=1, now=fixed_now)
    assert result == "{unknown}"


def test_preview_filename_extension_raw(config: CameraConfig) -> None:
    name = preview_filename("test_{seq:04d}", config, seq=1)
    assert name.endswith(".cr2")


def test_preview_filename_extension_jpeg() -> None:
    config = CameraConfig(capture_format=CaptureFormat.JPEG)
    name = preview_filename("test_{seq:04d}", config, seq=1)
    assert name.endswith(".jpg")


def test_bulb_exp_token(fixed_now: datetime) -> None:
    config = CameraConfig(
        shutter_speed=ShutterSpeed.BULB,
        bulb_duration_s=120.0,
    )
    result = render_filename("{exp}", config, seq=1, now=fixed_now)
    assert "120" in result

"""Shared pytest fixtures."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from picer.camera.mock_backend import MockBackend
from picer.camera.models import CameraConfig, CaptureFormat, ShutterSpeed
from picer.core.controller import CameraController


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "captures"


@pytest.fixture
def mock_backend() -> MockBackend:
    # sim_speed=0.0 → instant captures, no waiting in tests
    backend = MockBackend(sim_speed=0.0)
    backend.connect()
    return backend


@pytest.fixture
def controller(mock_backend: MockBackend) -> CameraController:
    ctrl = CameraController(mock_backend)
    # Backend already connected; bypass GVFS check by injecting directly
    ctrl._backend = mock_backend
    return ctrl


@pytest.fixture
def raw_config() -> CameraConfig:
    return CameraConfig(
        shutter_speed=ShutterSpeed.S_1,
        iso=400,
        capture_format=CaptureFormat.RAW,
    )


@pytest.fixture
def bulb_config() -> CameraConfig:
    return CameraConfig(
        shutter_speed=ShutterSpeed.BULB,
        iso=800,
        capture_format=CaptureFormat.RAW,
        bulb_duration_s=2.0,
    )

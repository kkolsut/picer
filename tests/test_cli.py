"""Tests for the CLI commands."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from picer.cli.commands import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_info_mock(runner: CliRunner) -> None:
    result = runner.invoke(main, ["info", "--mock"])
    assert result.exit_code == 0
    assert "mock" in result.output.lower() or "Camera" in result.output


def test_capture_mock(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, [
        "capture",
        "--exposure", "1",
        "--iso", "400",
        "--format", "raw",
        "--output", str(tmp_path),
        "--mock",
    ])
    assert result.exit_code == 0, result.output
    assert "Saved" in result.output


def test_sequence_mock(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, [
        "sequence",
        "--frames", "2",
        "--exposure", "1",
        "--iso", "400",
        "--output", str(tmp_path),
        "--mock",
    ])
    assert result.exit_code == 0, result.output
    assert "2" in result.output


def test_invalid_iso(runner: CliRunner) -> None:
    result = runner.invoke(main, [
        "capture",
        "--exposure", "1",
        "--iso", "999",
        "--output", "/tmp",
        "--mock",
    ])
    assert result.exit_code != 0
    assert "iso" in result.output.lower() or "Error" in result.output


def test_config_set_mock(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "set", "iso", "800", "--mock"])
    # Mock backend has set_config_widget? No — check graceful handling
    assert result.exit_code == 0 or "not supported" in result.output


def test_bulb_mode_cli(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, [
        "capture",
        "--exposure", "60",
        "--iso", "800",
        "--output", str(tmp_path),
        "--mock",
    ])
    assert result.exit_code == 0, result.output
    assert "Saved" in result.output

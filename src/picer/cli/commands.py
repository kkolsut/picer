"""picer CLI — astronomy camera control from the command line."""
from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table

from picer.camera.models import (
    ISO_VALUES,
    CameraConfig,
    CaptureFormat,
    FrameType,
    SequenceConfig,
    ShutterSpeed,
)

console = Console()
logger = logging.getLogger(__name__)


def _make_controller(mock: bool):
    from picer.core.controller import CameraController

    if mock:
        from picer.camera.mock_backend import MockBackend
        return CameraController(MockBackend(sim_speed=0.0))

    try:
        from picer.camera.gphoto2_backend import GPhoto2Backend
        return CameraController(GPhoto2Backend())
    except ImportError:
        console.print("[yellow]python-gphoto2 not installed — using mock backend[/yellow]")
        from picer.camera.mock_backend import MockBackend
        return CameraController(MockBackend(sim_speed=0.0))


def _parse_exposure(exposure: float) -> CameraConfig:
    """Convert an exposure in seconds to a CameraConfig with correct shutter/bulb."""
    config = CameraConfig()
    if exposure > 30:
        config.shutter_speed = ShutterSpeed.BULB
        config.bulb_duration_s = exposure
    else:
        config.shutter_speed = ShutterSpeed.from_seconds(exposure)
    return config


def _validate_iso(ctx, param, value):
    if value not in ISO_VALUES:
        raise click.BadParameter(f"must be one of {ISO_VALUES}")
    return value


def _validate_format(ctx, param, value):
    mapping = {
        "raw": CaptureFormat.RAW,
        "jpeg": CaptureFormat.JPEG,
        "jpg": CaptureFormat.JPEG,
        "raw+jpeg": CaptureFormat.RAW_JPEG,
        "raw+jpg": CaptureFormat.RAW_JPEG,
    }
    try:
        return mapping[value.lower()]
    except KeyError:
        raise click.BadParameter(f"must be one of: raw, jpeg, raw+jpeg")


def _validate_frame_type(ctx, param, value):
    try:
        return FrameType(value.lower())
    except ValueError:
        valid = ", ".join(ft.value for ft in FrameType)
        raise click.BadParameter(f"must be one of: {valid}")


# ── Shared options ─────────────────────────────────────────────────────────────

_common_options = [
    click.option("--exposure", "-e", required=True, type=float,
                 help="Exposure time in seconds. Values >30s use bulb mode."),
    click.option("--iso", "-i", default=400, type=int, callback=_validate_iso,
                 show_default=True, help=f"ISO value. One of: {ISO_VALUES}"),
    click.option("--format", "-f", "fmt", default="raw", callback=_validate_format,
                 show_default=True, help="File format: raw, jpeg, raw+jpeg"),
    click.option("--output", "-o", default=str(Path.home() / "picer_captures"),
                 show_default=True, type=click.Path(), help="Output directory"),
    click.option("--filename", default="{type}_{date}_{seq:04d}",
                 show_default=True, help="Filename template"),
    click.option("--type", "frame_type", default="light", callback=_validate_frame_type,
                 show_default=True, help="Frame type: light, dark, flat, bias"),
    click.option("--mock", is_flag=True, hidden=True, help="Use mock camera (no hardware)"),
]


def add_options(options):
    def decorator(f):
        for opt in reversed(options):
            f = opt(f)
        return f
    return decorator


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """Picer — astronomy DSLR capture tool for Canon EOS cameras."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


# ── picer info ────────────────────────────────────────────────────────────────

@main.command()
@click.option("--mock", is_flag=True, hidden=True)
def info(mock: bool) -> None:
    """Detect connected cameras and check GVFS status."""
    from picer.utils.gvfs_inhibit import gvfs_is_blocking_camera

    controller = _make_controller(mock)
    cameras = controller.list_cameras()

    table = Table(title="Connected Cameras", show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Camera")

    if cameras:
        for i, cam in enumerate(cameras):
            table.add_row(str(i), cam)
    else:
        table.add_row("-", "[dim]No cameras detected[/dim]")

    console.print(table)

    gvfs = gvfs_is_blocking_camera()
    gvfs_msg = (
        "[red]MOUNTED — camera may be inaccessible[/red]\n"
        "  Run: [bold]gio mount --unmount gphoto2://[/bold]"
        if gvfs
        else "[green]Not mounted (OK)[/green]"
    )
    console.print(f"\nGVFS status: {gvfs_msg}")


# ── picer capture ─────────────────────────────────────────────────────────────

@main.command()
@add_options(_common_options)
def capture(
    exposure: float,
    iso: int,
    fmt: CaptureFormat,
    output: str,
    filename: str,
    frame_type: FrameType,
    mock: bool,
) -> None:
    """Capture a single frame."""
    controller = _make_controller(mock)

    console.print(f"Connecting to camera…")
    ok, msg = controller.connect()
    if not ok:
        console.print(f"[red]Error:[/red] {msg}")
        sys.exit(1)

    config = _parse_exposure(exposure)
    config.iso = iso
    config.capture_format = fmt

    output_dir = Path(output)
    mode = "BULB" if config.shutter_speed == ShutterSpeed.BULB else f"{config.shutter_speed.value}s"
    console.print(f"Capturing: {mode} | ISO {iso} | {fmt.label} | {frame_type.label}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task: Optional[TaskID] = None
        if config.shutter_speed == ShutterSpeed.BULB:
            task = progress.add_task("Bulb exposure", total=config.bulb_duration_s)

        def on_progress(p):
            if task is not None:
                progress.update(task, completed=p.elapsed_s)

        try:
            result = controller.capture(
                config=config,
                output_dir=output_dir,
                filename_template=filename,
                frame_type=frame_type,
                on_progress=on_progress,
            )
        except Exception as exc:
            console.print(f"[red]Capture failed:[/red] {exc}")
            sys.exit(1)

    console.print(f"[green]✓[/green] Saved: [bold]{result.file_path}[/bold]")
    controller.disconnect()


# ── picer sequence ────────────────────────────────────────────────────────────

@main.command()
@add_options(_common_options)
@click.option("--frames", "-n", default=1, show_default=True, type=int,
              help="Number of frames to capture")
@click.option("--interval", default=0.0, show_default=True, type=float,
              help="Start-to-start interval in seconds (0 = back-to-back)")
@click.option("--on-error", "on_error", default="continue",
              type=click.Choice(["continue", "abort"]), show_default=True,
              help="Action on capture error")
def sequence(
    exposure: float,
    iso: int,
    fmt: CaptureFormat,
    output: str,
    filename: str,
    frame_type: FrameType,
    mock: bool,
    frames: int,
    interval: float,
    on_error: str,
) -> None:
    """Run a multi-frame capture sequence."""
    controller = _make_controller(mock)

    console.print("Connecting to camera…")
    ok, msg = controller.connect()
    if not ok:
        console.print(f"[red]Error:[/red] {msg}")
        sys.exit(1)

    config = _parse_exposure(exposure)
    config.iso = iso
    config.capture_format = fmt

    seq_config = SequenceConfig(
        frame_count=frames,
        interval_s=interval,
        output_dir=Path(output),
        filename_template=filename,
        frame_type=frame_type,
        camera_config=config,
    )

    total_s = config.effective_exposure_s * frames + max(0, interval - config.effective_exposure_s) * (frames - 1)
    console.print(
        f"Sequence: [bold]{frames}[/bold] frames | "
        f"[bold]{exposure}s[/bold] exposure | "
        f"ISO [bold]{iso}[/bold] | "
        f"Format [bold]{fmt.label}[/bold] | "
        f"Type [bold]{frame_type.label}[/bold]"
    )

    results = []
    errors = []

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} frames"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        seq_task = progress.add_task("Sequence", total=frames)
        bulb_task: Optional[TaskID] = None
        if config.shutter_speed == ShutterSpeed.BULB:
            bulb_task = progress.add_task("  Exposure", total=config.bulb_duration_s)

        done_event = threading.Event()

        def on_frame_start(idx, total):
            progress.update(seq_task, description=f"Frame {idx + 1}/{total}")
            if bulb_task is not None:
                progress.reset(bulb_task)

        def on_bulb_progress(p):
            if bulb_task is not None:
                progress.update(bulb_task, completed=p.elapsed_s)

        def on_frame_complete(result):
            results.append(result)
            progress.advance(seq_task)

        def on_seq_error(idx, exc):
            errors.append((idx, exc))
            console.print(f"[red]  Frame {idx + 1} error:[/red] {exc}")
            return on_error == "continue"

        def on_complete(all_results):
            done_event.set()

        controller.start_sequence(
            config=seq_config,
            on_frame_start=on_frame_start,
            on_frame_complete=on_frame_complete,
            on_bulb_progress=on_bulb_progress,
            on_error=on_seq_error,
            on_sequence_complete=on_complete,
        )

        done_event.wait()

    console.print(f"\n[green]✓[/green] Sequence complete: [bold]{len(results)}[/bold] frame(s) captured")
    if errors:
        console.print(f"[yellow]  {len(errors)} error(s)[/yellow]")
    controller.disconnect()


# ── picer config set ──────────────────────────────────────────────────────────

@main.command("config")
@click.argument("action", type=click.Choice(["set"]))
@click.argument("key")
@click.argument("value")
@click.option("--mock", is_flag=True, hidden=True)
def config_cmd(action: str, key: str, value: str, mock: bool) -> None:
    """Set a raw gphoto2 config widget. Example: picer config set iso 800"""
    controller = _make_controller(mock)
    ok, msg = controller.connect()
    if not ok:
        console.print(f"[red]Error:[/red] {msg}")
        sys.exit(1)

    try:
        backend = controller._backend
        if hasattr(backend, "set_config_widget"):
            backend.set_config_widget(key, value)
            console.print(f"[green]✓[/green] Set [bold]{key}[/bold] = [bold]{value}[/bold]")
        else:
            console.print("[yellow]Config set not supported by this backend[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)
    finally:
        controller.disconnect()


# ── picer gui ─────────────────────────────────────────────────────────────────

@main.command()
@click.option("--mock", is_flag=True, help="Use mock camera (no hardware needed)")
def gui(mock: bool) -> None:
    """Launch the graphical interface."""
    from picer.gui.app import main as gui_main
    args = ["picer-gui"]
    if mock:
        args.append("--mock")
    sys.exit(gui_main(args))

"""Sequence endpoints and WebSocket progress stream."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from picer.api import state
from picer.api.auth import require_auth
from picer.api.routes.capture import _parse_camera_config
from picer.camera.models import (
    CaptureResult,
    FrameType,
    ObservationMetadata,
    SequenceConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sequence"])

# Keepalive interval for idle WebSocket connections (seconds)
_WS_KEEPALIVE = 25.0


@router.post("/sequence")
def start_sequence(body: dict, user: Annotated[str, Depends(require_auth)]):
    """Start a capture sequence. Returns 409 if camera is not connected or sequence is already running."""
    if not state.controller.is_connected():
        raise HTTPException(409, "Camera not connected")
    if state.controller.is_sequence_running():
        raise HTTPException(409, "A sequence is already running")

    state.session.touch()

    seq_cfg = _parse_sequence_config(body)

    # Map frame_index → capture_id so on_fits_ready can update the record
    frame_capture_ids: dict[int, str] = {}

    state.session.set_sequence_running(True)

    def on_frame_start(idx: int, total: int) -> None:
        state.event_bus.publish(
            {"event": "frame_start", "frame": idx + 1, "total": total}
        )

    def on_frame_complete(result: CaptureResult) -> None:
        capture_id = state.captures.add(result)
        frame_capture_ids[result.frame_index] = capture_id
        state.event_bus.publish(
            {
                "event": "frame_complete",
                "frame": result.frame_index + 1,
                "file": result.file_path.name,
                "capture_id": capture_id,
            }
        )

    def on_bulb_progress(p) -> None:
        state.event_bus.publish(
            {
                "event": "bulb_progress",
                "elapsed_s": round(p.elapsed_s, 1),
                "total_s": round(p.total_s, 1),
            }
        )

    def on_error(idx: int, exc: Exception) -> bool:
        state.event_bus.publish(
            {"event": "frame_error", "frame": idx + 1, "error": str(exc)}
        )
        return not isinstance(exc, ValueError)

    def on_sequence_complete(results: list) -> None:
        state.session.set_sequence_running(False)
        state.event_bus.publish(
            {"event": "sequence_complete", "frames": len(results)}
        )

    def on_fits_ready(result: CaptureResult, paths: dict) -> None:
        capture_id = frame_capture_ids.get(result.frame_index)
        if capture_id:
            record = state.captures.get(capture_id)
            if record is not None:
                record.fits_paths = {
                    k: Path(v) if isinstance(v, str) else v
                    for k, v in paths.items()
                }
        state.event_bus.publish(
            {
                "event": "fits_ready",
                "frame": result.frame_index + 1,
                "capture_id": capture_id,
                "paths": {k: str(v) for k, v in paths.items()},
            }
        )

    try:
        state.controller.start_sequence(
            config=seq_cfg,
            on_frame_start=on_frame_start,
            on_frame_complete=on_frame_complete,
            on_bulb_progress=on_bulb_progress,
            on_error=on_error,
            on_sequence_complete=on_sequence_complete,
            on_fits_ready=on_fits_ready,
        )
    except RuntimeError as exc:
        state.session.set_sequence_running(False)
        raise HTTPException(409, str(exc))

    return {"status": "started", "frame_count": seq_cfg.frame_count}


@router.delete("/sequence")
def stop_sequence(user: Annotated[str, Depends(require_auth)]):
    """Stop a running sequence."""
    if not state.controller.is_sequence_running():
        raise HTTPException(409, "No sequence is running")

    state.controller.stop_sequence()
    state.session.set_sequence_running(False)
    return {"status": "stopped"}


@router.websocket("/sequence/progress")
async def sequence_progress_ws(websocket: WebSocket):
    """WebSocket stream of sequence progress events.

    Events: frame_start, frame_complete, bulb_progress, fits_ready,
            frame_error, sequence_complete, ping (keepalive).
    """
    await websocket.accept()

    async with state.event_bus.subscribe() as queue:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_WS_KEEPALIVE)
                except asyncio.TimeoutError:
                    # Send keepalive so the connection stays open
                    try:
                        await websocket.send_text(json.dumps({"event": "ping"}))
                    except Exception:
                        break
                    continue

                await websocket.send_text(json.dumps(event))

                if event.get("event") == "sequence_complete":
                    break

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.error("WebSocket error: %s", exc)


def _parse_sequence_config(body: dict) -> SequenceConfig:
    cfg = SequenceConfig()
    cfg.frame_count = int(body.get("frame_count", 1))
    cfg.interval_s = float(body.get("interval_s", 0.0))

    try:
        cfg.frame_type = FrameType(body.get("frame_type", "light"))
    except ValueError:
        cfg.frame_type = FrameType.LIGHT

    cfg.camera_config = _parse_camera_config(body.get("camera_config", {}))

    cfg.output_dir = Path(body.get("output_dir", str(Path.home() / "picer_captures")))
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    cfg.filename_template = body.get("filename_template", "{type}_{date}_{seq:04d}")

    obs = body.get("observation")
    if obs:
        cfg.observation = ObservationMetadata(
            object_name=obs.get("object_name"),
            ra_deg=obs.get("ra_deg"),
            dec_deg=obs.get("dec_deg"),
            observer_lat=obs.get("observer_lat"),
            observer_lon=obs.get("observer_lon"),
            telescope=obs.get("telescope"),
            detector=obs.get("detector"),
            focal_mm=obs.get("focal_mm"),
            aperture_mm=obs.get("aperture_mm"),
            pixel_um=obs.get("pixel_um"),
            frame_type=obs.get("frame_type"),
        )

    return cfg

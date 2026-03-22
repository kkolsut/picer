"""Camera connection and status endpoints."""
from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from picer.api import state
from picer.api.auth import require_auth

router = APIRouter(tags=["camera"])


@router.get("/cameras")
def list_cameras(user: Annotated[str, Depends(require_auth)]):
    """List cameras detected via gphoto2."""
    return {"cameras": state.controller.list_cameras()}


@router.post("/connect")
def connect_camera(user: Annotated[str, Depends(require_auth)]):
    """Acquire session and connect to the camera. Returns 409 if already taken."""
    if not state.session.acquire():
        raise HTTPException(409, "Camera session already active")

    ok, msg = state.controller.connect()
    if not ok:
        state.session.release()
        raise HTTPException(503, f"Could not connect to camera: {msg}")

    return {"status": "connected"}


@router.delete("/connect")
def disconnect_camera(user: Annotated[str, Depends(require_auth)]):
    """Disconnect the camera and release the session."""
    if not state.session.is_held():
        raise HTTPException(409, "No active session")
    if state.controller.is_sequence_running():
        raise HTTPException(409, "Cannot disconnect while a sequence is running")

    state.controller.disconnect()
    state.session.release()
    return {"status": "disconnected"}


@router.get("/status")
def get_status(user: Annotated[str, Depends(require_auth)]):
    """Return connection state and disk usage."""
    state.session.touch()
    disk = shutil.disk_usage("/")
    low_disk = disk.free < 1 * 1024 ** 3  # < 1 GB free
    return {
        "connected": state.controller.is_connected(),
        "session_active": state.session.is_held(),
        "sequence_running": state.controller.is_sequence_running(),
        "disk_free_gb": round(disk.free / 1024 ** 3, 2),
        "low_disk": low_disk,
    }

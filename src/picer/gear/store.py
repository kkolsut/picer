"""Persistent gear storage: ~/.config/picer/gear.json.

Only user-added custom entries and the current selection are stored.
The built-in catalog (picer.gear.catalog) is never written to disk.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from picer.gear.catalog import CAMERAS, OPTICS
from picer.gear.models import GearCamera, GearOptic

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "picer" / "gear.json"


def _load_raw() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as exc:
        logger.warning("Could not read gear.json: %s", exc)
        return {}


def _save_raw(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def load_gear() -> tuple[list[GearCamera], list[GearOptic], Optional[str], Optional[str]]:
    """Return (cameras, optics, selected_camera_name, selected_optic_name).

    Merges built-in catalog with user custom entries. Built-in entries come first.
    """
    data = _load_raw()

    custom_cameras = [
        GearCamera(
            name=c["name"],
            sensor_w_mm=c["sensor_w_mm"],
            sensor_h_mm=c["sensor_h_mm"],
            pixels_x=c["pixels_x"],
            pixels_y=c["pixels_y"],
            pixel_um=c["pixel_um"],
            custom=True,
        )
        for c in data.get("cameras", [])
    ]
    custom_optics = [
        GearOptic(
            name=o["name"],
            focal_mm=o["focal_mm"],
            aperture_mm=o["aperture_mm"],
            custom=True,
        )
        for o in data.get("optics", [])
    ]

    cameras = CAMERAS + custom_cameras
    optics = OPTICS + custom_optics

    return cameras, optics, data.get("selected_camera"), data.get("selected_optic")


def save_selection(selected_camera: Optional[str], selected_optic: Optional[str]) -> None:
    data = _load_raw()
    data["selected_camera"] = selected_camera
    data["selected_optic"] = selected_optic
    _save_raw(data)


def add_custom_camera(cam: GearCamera) -> None:
    data = _load_raw()
    cameras = data.get("cameras", [])
    cameras.append({
        "name": cam.name,
        "sensor_w_mm": cam.sensor_w_mm,
        "sensor_h_mm": cam.sensor_h_mm,
        "pixels_x": cam.pixels_x,
        "pixels_y": cam.pixels_y,
        "pixel_um": cam.pixel_um,
        "custom": True,
    })
    data["cameras"] = cameras
    _save_raw(data)


def update_custom_camera(old_name: str, cam: GearCamera) -> None:
    data = _load_raw()
    cameras = data.get("cameras", [])
    for i, c in enumerate(cameras):
        if c["name"] == old_name:
            cameras[i] = {
                "name": cam.name,
                "sensor_w_mm": cam.sensor_w_mm,
                "sensor_h_mm": cam.sensor_h_mm,
                "pixels_x": cam.pixels_x,
                "pixels_y": cam.pixels_y,
                "pixel_um": cam.pixel_um,
                "custom": True,
            }
            break
    data["cameras"] = cameras
    if data.get("selected_camera") == old_name:
        data["selected_camera"] = cam.name
    _save_raw(data)


def update_custom_optic(old_name: str, optic: GearOptic) -> None:
    data = _load_raw()
    optics = data.get("optics", [])
    for i, o in enumerate(optics):
        if o["name"] == old_name:
            optics[i] = {
                "name": optic.name,
                "focal_mm": optic.focal_mm,
                "aperture_mm": optic.aperture_mm,
                "custom": True,
            }
            break
    data["optics"] = optics
    if data.get("selected_optic") == old_name:
        data["selected_optic"] = optic.name
    _save_raw(data)


def add_custom_optic(optic: GearOptic) -> None:
    data = _load_raw()
    optics = data.get("optics", [])
    optics.append({
        "name": optic.name,
        "focal_mm": optic.focal_mm,
        "aperture_mm": optic.aperture_mm,
        "custom": True,
    })
    data["optics"] = optics
    _save_raw(data)

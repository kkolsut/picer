"""Gear catalog CRUD endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import picer.gear.store as gear_store
from picer.api.auth import require_auth
from picer.gear.catalog import CAMERAS as BUILTIN_CAMERAS, OPTICS as BUILTIN_OPTICS
from picer.gear.models import GearCamera, GearOptic

router = APIRouter(prefix="/gear", tags=["gear"])


class CameraBody(BaseModel):
    name: str
    sensor_w_mm: float
    sensor_h_mm: float
    pixels_x: int
    pixels_y: int
    pixel_um: float


class OpticBody(BaseModel):
    name: str
    focal_mm: float
    aperture_mm: float


class SelectionBody(BaseModel):
    camera: str | None = None
    optic: str | None = None


# ── Cameras ───────────────────────────────────────────────────────────────────

@router.get("/cameras")
def list_cameras(user: Annotated[str, Depends(require_auth)]):
    cameras, _, _, _ = gear_store.load_gear()
    return {"cameras": [_camera_dict(c) for c in cameras]}


@router.post("/cameras", status_code=201)
def add_camera(body: CameraBody, user: Annotated[str, Depends(require_auth)]):
    cam = GearCamera(**body.model_dump(), custom=True)
    gear_store.add_custom_camera(cam)
    return _camera_dict(cam)


@router.patch("/cameras/{name}")
def update_camera(
    name: str, body: CameraBody, user: Annotated[str, Depends(require_auth)]
):
    cameras, _, _, _ = gear_store.load_gear()
    if not any(c.name == name and c.custom for c in cameras):
        raise HTTPException(404, f"Custom camera '{name}' not found")
    cam = GearCamera(**body.model_dump(), custom=True)
    gear_store.update_custom_camera(name, cam)
    return _camera_dict(cam)


@router.delete("/cameras/{name}", status_code=204)
def delete_camera(name: str, user: Annotated[str, Depends(require_auth)]):
    cameras, _, _, _ = gear_store.load_gear()
    if not any(c.name == name and c.custom for c in cameras):
        raise HTTPException(404, f"Custom camera '{name}' not found")
    gear_store.delete_custom_camera(name)


# ── Optics ────────────────────────────────────────────────────────────────────

@router.get("/optics")
def list_optics(user: Annotated[str, Depends(require_auth)]):
    _, optics, _, _ = gear_store.load_gear()
    return {"optics": [_optic_dict(o) for o in optics]}


@router.post("/optics", status_code=201)
def add_optic(body: OpticBody, user: Annotated[str, Depends(require_auth)]):
    optic = GearOptic(**body.model_dump(), custom=True)
    gear_store.add_custom_optic(optic)
    return _optic_dict(optic)


@router.patch("/optics/{name}")
def update_optic(
    name: str, body: OpticBody, user: Annotated[str, Depends(require_auth)]
):
    _, optics, _, _ = gear_store.load_gear()
    if not any(o.name == name and o.custom for o in optics):
        raise HTTPException(404, f"Custom optic '{name}' not found")
    optic = GearOptic(**body.model_dump(), custom=True)
    gear_store.update_custom_optic(name, optic)
    return _optic_dict(optic)


@router.delete("/optics/{name}", status_code=204)
def delete_optic(name: str, user: Annotated[str, Depends(require_auth)]):
    _, optics, _, _ = gear_store.load_gear()
    if not any(o.name == name and o.custom for o in optics):
        raise HTTPException(404, f"Custom optic '{name}' not found")
    gear_store.delete_custom_optic(name)


# ── Selection ─────────────────────────────────────────────────────────────────

@router.get("/selection")
def get_selection(user: Annotated[str, Depends(require_auth)]):
    _, _, selected_camera, selected_optic = gear_store.load_gear()
    return {"camera": selected_camera, "optic": selected_optic}


@router.put("/selection")
def set_selection(body: SelectionBody, user: Annotated[str, Depends(require_auth)]):
    gear_store.save_selection(body.camera, body.optic)
    return {"camera": body.camera, "optic": body.optic}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _camera_dict(c: GearCamera) -> dict:
    return {
        "name": c.name,
        "sensor_w_mm": c.sensor_w_mm,
        "sensor_h_mm": c.sensor_h_mm,
        "pixels_x": c.pixels_x,
        "pixels_y": c.pixels_y,
        "pixel_um": c.pixel_um,
        "custom": c.custom,
    }


def _optic_dict(o: GearOptic) -> dict:
    return {
        "name": o.name,
        "focal_mm": o.focal_mm,
        "aperture_mm": o.aperture_mm,
        "custom": o.custom,
    }

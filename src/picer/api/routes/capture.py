"""Single-frame capture endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from picer.api import state
from picer.api.auth import require_auth
from picer.camera.models import CameraConfig, CaptureFormat, FrameType, ShutterSpeed
from picer.utils.psf import compute_psf

router = APIRouter(tags=["capture"])


@router.post("/capture")
def single_capture(body: dict, user: Annotated[str, Depends(require_auth)]):
    """Trigger a single capture. Returns capture metadata including an ID."""
    if not state.controller.is_connected():
        raise HTTPException(409, "Camera not connected")

    state.session.touch()

    cfg = _parse_camera_config(body.get("camera_config", {}))
    output_dir = Path(body.get("output_dir", str(Path.home() / "picer_captures")))
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_type_str = body.get("frame_type", "light")
    try:
        frame_type = FrameType(frame_type_str)
    except ValueError:
        frame_type = FrameType.LIGHT

    template = body.get("filename_template", "{type}_{date}_{seq:04d}")

    try:
        result = state.controller.capture(
            config=cfg,
            output_dir=output_dir,
            filename_template=template,
            frame_type=frame_type,
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))

    capture_id = state.captures.add(result)
    return {
        "id": capture_id,
        "file": result.file_path.name,
        "exposure_s": result.exposure_s,
        "iso": result.iso,
        "timestamp": result.timestamp,
    }


@router.get("/captures/{capture_id}/raw")
def download_raw(capture_id: str, user: Annotated[str, Depends(require_auth)]):
    """Download the original RAW file."""
    state.session.touch()
    record = state.captures.get(capture_id)
    if record is None:
        raise HTTPException(404, "Capture not found")
    path = record.result.file_path
    if not path.exists():
        raise HTTPException(404, "File not found on disk")
    return FileResponse(
        path, media_type="application/octet-stream", filename=path.name
    )


@router.get("/captures/{capture_id}/preview.jpg")
def capture_preview(capture_id: str, user: Annotated[str, Depends(require_auth)]):
    """Return a JPEG preview of the capture (from FITS G channel or raw CR2)."""
    state.session.touch()
    record = state.captures.get(capture_id)
    if record is None:
        raise HTTPException(404, "Capture not found")

    g_path = record.fits_paths.get("G")
    if g_path and g_path.exists():
        from picer.api.preview import fits_to_jpeg
        jpeg_bytes = fits_to_jpeg(g_path)
    else:
        raw_path = record.result.file_path
        if not raw_path.exists():
            raise HTTPException(404, "File not found on disk")
        from picer.api.preview import cr2_to_jpeg
        jpeg_bytes = cr2_to_jpeg(raw_path)

    return Response(jpeg_bytes, media_type="image/jpeg")


@router.delete("/captures/{capture_id}", status_code=204)
def delete_capture(capture_id: str, user: Annotated[str, Depends(require_auth)]):
    """Delete a capture and its associated files from disk."""
    record = state.captures.get(capture_id)
    if record is None:
        raise HTTPException(404, "Capture not found")

    try:
        path = record.result.file_path
        if path.exists():
            path.unlink()
        for fits_path in record.fits_paths.values():
            if fits_path.exists():
                fits_path.unlink()
    except Exception as exc:
        raise HTTPException(500, f"Could not delete file: {exc}")

    state.captures.delete(capture_id)


@router.get("/captures/{capture_id}/fits/{channel}")
def download_fits(
    capture_id: str,
    channel: str,
    user: Annotated[str, Depends(require_auth)],
):
    """Download a FITS channel file (R, G, or B)."""
    state.session.touch()
    record = state.captures.get(capture_id)
    if record is None:
        raise HTTPException(404, "Capture not found")

    channel = channel.upper()
    path = record.fits_paths.get(channel)
    if not path or not path.exists():
        raise HTTPException(404, f"FITS channel {channel} not available")

    return FileResponse(
        path,
        media_type="application/fits",
        filename=path.name,
    )


@router.get("/captures/{capture_id}/psf")
def capture_psf(
    capture_id: str,
    x: int,
    y: int,
    user: Annotated[str, Depends(require_auth)],
):
    """Run PSF/FWHM analysis at pixel (x, y) in the FITS G channel."""
    state.session.touch()
    record = state.captures.get(capture_id)
    if record is None:
        raise HTTPException(404, "Capture not found")

    g_path = record.fits_paths.get("G")
    if not g_path or not g_path.exists():
        raise HTTPException(409, "FITS file not available for this capture")

    psf = compute_psf(g_path, x, y)
    return {
        "fit_ok": psf.fit_ok,
        "fit_error": psf.fit_error,
        "fwhm_px": psf.fwhm_px,
        "sigma_px": psf.sigma_px,
        "amplitude": psf.amplitude,
        "background": psf.background,
        "fits_x": psf.fits_x,
        "fits_y": psf.fits_y,
        "r_values": psf.r_values,
        "i_values": psf.i_values,
    }


def _parse_camera_config(d: dict[str, Any]) -> CameraConfig:
    cfg = CameraConfig()
    if "shutter_speed" in d:
        try:
            cfg.shutter_speed = ShutterSpeed(d["shutter_speed"])
        except ValueError:
            pass
    if "iso" in d:
        cfg.iso = int(d["iso"])
    if "capture_format" in d:
        try:
            cfg.capture_format = CaptureFormat(d["capture_format"])
        except ValueError:
            pass
    if "bulb_duration_s" in d:
        cfg.bulb_duration_s = float(d["bulb_duration_s"])
    return cfg

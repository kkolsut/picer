"""HTTP + WebSocket client for the Picer API server.

Provides the same interface as CameraController so the GTK GUI can work
with a remote (or local) picer-api instance without knowing the difference.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class APIClient:
    """Thin client that wraps the Picer REST API and WebSocket stream."""

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        username: str = "picer",
        password: str = "",
    ) -> None:
        import httpx

        self._base = base_url.rstrip("/")
        self._ws_base = (
            self._base.replace("https://", "wss://").replace("http://", "ws://")
        )
        auth = (username, password) if password else None
        self._http = httpx.Client(
            base_url=self._base, auth=auth, timeout=30.0
        )
        self._seq_running = False

    # ------------------------------------------------------------------
    # CameraController-compatible interface
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        try:
            return self._http.get("/status").json().get("connected", False)
        except Exception:
            return False

    def connect(self) -> tuple[bool, str]:
        try:
            r = self._http.post("/connect")
            if r.status_code == 200:
                return True, ""
            return False, r.json().get("detail", f"HTTP {r.status_code}")
        except Exception as exc:
            return False, str(exc)

    def disconnect(self) -> None:
        try:
            self._http.delete("/connect")
        except Exception:
            pass

    def list_cameras(self) -> list[str]:
        try:
            return self._http.get("/cameras").json().get("cameras", [])
        except Exception:
            return []

    def is_sequence_running(self) -> bool:
        try:
            return self._http.get("/status").json().get("sequence_running", False)
        except Exception:
            return self._seq_running

    def start_sequence(
        self,
        config,
        on_frame_start: Optional[Callable] = None,
        on_frame_complete: Optional[Callable] = None,
        on_bulb_progress: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_sequence_complete: Optional[Callable] = None,
        on_fits_ready: Optional[Callable] = None,
    ) -> None:
        """POST /sequence then start WebSocket listener in a daemon thread."""
        body = _seq_config_to_dict(config)
        r = self._http.post("/sequence", json=body)
        r.raise_for_status()

        self._seq_running = True
        callbacks = {
            "on_frame_start": on_frame_start,
            "on_frame_complete": on_frame_complete,
            "on_bulb_progress": on_bulb_progress,
            "on_error": on_error,
            "on_sequence_complete": on_sequence_complete,
            "on_fits_ready": on_fits_ready,
        }
        t = threading.Thread(
            target=self._run_ws_listener, args=(callbacks,), daemon=True
        )
        t.start()

    def stop_sequence(self) -> None:
        self._seq_running = False
        try:
            self._http.delete("/sequence")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Gear API
    # ------------------------------------------------------------------

    def get_gear(self):
        """Return (cameras, optics, selected_camera_name, selected_optic_name)."""
        from picer.gear.models import GearCamera, GearOptic

        cameras_raw = self._http.get("/gear/cameras").json().get("cameras", [])
        optics_raw = self._http.get("/gear/optics").json().get("optics", [])
        sel = self._http.get("/gear/selection").json()

        cameras = [GearCamera(**d) for d in cameras_raw]
        optics = [GearOptic(**d) for d in optics_raw]
        return cameras, optics, sel.get("camera"), sel.get("optic")

    def save_gear_selection(
        self, camera: Optional[str], optic: Optional[str]
    ) -> None:
        self._http.put("/gear/selection", json={"camera": camera, "optic": optic})

    def add_gear_camera(self, cam) -> None:
        self._http.post("/gear/cameras", json=_camera_to_dict(cam))

    def update_gear_camera(self, old_name: str, cam) -> None:
        import urllib.parse
        self._http.patch(f"/gear/cameras/{urllib.parse.quote(old_name)}", json=_camera_to_dict(cam))

    def delete_gear_camera(self, name: str) -> None:
        import urllib.parse
        self._http.delete(f"/gear/cameras/{urllib.parse.quote(name)}")

    def add_gear_optic(self, optic) -> None:
        self._http.post("/gear/optics", json=_optic_to_dict(optic))

    def update_gear_optic(self, old_name: str, optic) -> None:
        import urllib.parse
        self._http.patch(f"/gear/optics/{urllib.parse.quote(old_name)}", json=_optic_to_dict(optic))

    def delete_gear_optic(self, name: str) -> None:
        import urllib.parse
        self._http.delete(f"/gear/optics/{urllib.parse.quote(name)}")

    # ------------------------------------------------------------------
    # Object / observer API
    # ------------------------------------------------------------------

    def get_observer(self) -> tuple:
        """Return (catalog, designation, lat, lon) — same as objects.store.load_observer."""
        sel = self._http.get("/objects/selection").json()
        loc = self._http.get("/objects/location").json()
        return (
            sel.get("catalog"),
            sel.get("designation"),
            loc.get("lat"),
            loc.get("lon"),
        )

    def save_selection(self, catalog: Optional[str], designation: Optional[str]) -> None:
        self._http.put(
            "/objects/selection", json={"catalog": catalog, "designation": designation}
        )

    def save_location(self, lat: Optional[float], lon: Optional[float]) -> None:
        if lat is None or lon is None:
            return
        self._http.put("/objects/location", json={"lat": lat, "lon": lon})

    def search_object(self, catalog: str, query: str):
        """Return DeepSkyObject or None."""
        from picer.objects.models import DeepSkyObject
        try:
            r = self._http.get(
                "/objects/search", params={"catalog": catalog, "q": query}
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            d = r.json()
            return DeepSkyObject(
                catalog=d["catalog"],
                designation=d["designation"],
                name=d["name"],
                obj_type=d["obj_type"],
                constellation=d["constellation"],
                ra_deg=d["ra_deg"],
                dec_deg=d["dec_deg"],
            )
        except Exception as exc:
            logger.debug("search_object failed: %s", exc)
            return None

    def get_favorites(self) -> list[dict]:
        try:
            return self._http.get("/objects/favorites").json().get("favorites", [])
        except Exception:
            return []

    def add_favorite(self, name: str, lat: float, lon: float) -> None:
        self._http.post(
            "/objects/favorites", json={"name": name, "lat": lat, "lon": lon}
        )

    def remove_favorite(self, name: str) -> None:
        import urllib.parse
        self._http.delete(f"/objects/favorites/{urllib.parse.quote(name)}")

    def get_catalog_keys(self) -> list[str]:
        try:
            catalogs = self._http.get("/objects/catalogs").json().get("catalogs", [])
            return [c["key"] for c in catalogs]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # File download
    # ------------------------------------------------------------------

    def download_fits_channel(self, capture_id: str, channel: str) -> bytes:
        r = self._http.get(
            f"/captures/{capture_id}/fits/{channel.upper()}", timeout=120.0
        )
        r.raise_for_status()
        return r.content

    def list_captures(self) -> list[dict]:
        """Return list of capture dicts from the server session."""
        r = self._http.get("/captures")
        r.raise_for_status()
        return r.json().get("captures", [])

    def list_server_files(self, dir: Optional[str] = None) -> dict:
        """Scan a server directory for CR2+FITS files. Returns {dir, files}."""
        params = {"dir": dir} if dir else {}
        r = self._http.get("/files", params=params)
        r.raise_for_status()
        return r.json()

    def download_file_path(self, server_path: str) -> tuple[bytes, str]:
        """Download any CR2 or FITS file by its absolute path on the server."""
        r = self._http.get("/files/download", params={"path": server_path}, timeout=120.0)
        r.raise_for_status()
        cd = r.headers.get("content-disposition", "")
        filename = Path(server_path).name
        if 'filename="' in cd:
            filename = cd.split('filename="')[1].rstrip('"')
        return r.content, filename

    def delete_file_path(self, server_path: str) -> None:
        """Delete a single CR2 or FITS file on the server by path."""
        self._http.delete("/files/delete", params={"path": server_path})

    def download_raw(self, capture_id: str) -> tuple[bytes, str]:
        """Return (file_bytes, filename) for the original RAW file."""
        r = self._http.get(f"/captures/{capture_id}/raw", timeout=120.0)
        r.raise_for_status()
        cd = r.headers.get("content-disposition", "")
        filename = f"{capture_id}.bin"
        if 'filename="' in cd:
            filename = cd.split('filename="')[1].rstrip('"')
        return r.content, filename

    def delete_capture(self, capture_id: str) -> None:
        self._http.delete(f"/captures/{capture_id}")

    def check_reachable(self) -> tuple[bool, str]:
        """Return (ok, error_message). Quick connectivity check."""
        try:
            r = self._http.get("/status", timeout=5.0)
            if r.status_code < 500:
                return True, ""
            return False, f"Server error: HTTP {r.status_code}"
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # WebSocket listener
    # ------------------------------------------------------------------

    def _run_ws_listener(self, callbacks: dict) -> None:
        import asyncio

        try:
            asyncio.run(self._async_ws(callbacks))
        except Exception as exc:
            logger.error("WS listener crashed: %s", exc)
        finally:
            self._seq_running = False

    async def _async_ws(self, callbacks: dict) -> None:
        import websockets

        uri = f"{self._ws_base}/sequence/progress"
        logger.debug("Connecting to WS: %s", uri)

        try:
            async with websockets.connect(uri, ping_interval=20) as ws:
                async for raw in ws:
                    try:
                        event = json.loads(raw)
                    except Exception:
                        continue

                    evt = event.get("event")
                    if evt == "ping":
                        continue

                    logger.debug("WS event: %s", evt)
                    self._dispatch_event(event, callbacks)

                    if evt == "sequence_complete":
                        break
        except Exception as exc:
            logger.error("WS error: %s", exc)

    def _dispatch_event(self, event: dict, callbacks: dict) -> None:
        from picer.camera.models import BulbProgress, CaptureResult

        evt = event.get("event")

        if evt == "frame_start":
            cb = callbacks.get("on_frame_start")
            if cb:
                cb(event["frame"] - 1, event["total"])

        elif evt == "frame_complete":
            cb = callbacks.get("on_frame_complete")
            if cb:
                result = CaptureResult(
                    frame_index=event["frame"] - 1,
                    file_path=Path(event["file"]),
                    exposure_s=event.get("exposure_s", 0.0),
                    iso=event.get("iso", 0),
                    timestamp=time.time(),
                )
                cb(result)

        elif evt == "bulb_progress":
            cb = callbacks.get("on_bulb_progress")
            if cb:
                cb(BulbProgress(
                    elapsed_s=event["elapsed_s"],
                    total_s=event["total_s"],
                ))

        elif evt == "frame_error":
            cb = callbacks.get("on_error")
            if cb:
                cb(event.get("frame", 1) - 1, RuntimeError(event.get("error", "")))

        elif evt == "sequence_complete":
            self._seq_running = False
            cb = callbacks.get("on_sequence_complete")
            if cb:
                cb([])  # full results list not available from WS

        elif evt == "fits_ready":
            cb = callbacks.get("on_fits_ready")
            if cb:
                # Different signature from standalone: (capture_id, exposure_s, iso)
                cb(
                    event["capture_id"],
                    event.get("exposure_s", 0.0),
                    event.get("iso", 0),
                )


# ------------------------------------------------------------------
# Serialisation helpers
# ------------------------------------------------------------------

def _seq_config_to_dict(config) -> dict:
    from picer.camera.models import ShutterSpeed

    cfg = config.camera_config
    body: dict = {
        "frame_count": config.frame_count,
        "interval_s": config.interval_s,
        "frame_type": config.frame_type.value,
        "output_dir": str(config.output_dir),
        "filename_template": config.filename_template,
        "camera_config": {
            "shutter_speed": cfg.shutter_speed.value,
            "iso": cfg.iso,
            "capture_format": cfg.capture_format.value,
            "bulb_duration_s": cfg.bulb_duration_s,
        },
    }
    obs = config.observation
    if obs:
        body["observation"] = {
            k: v for k, v in {
                "object_name": obs.object_name,
                "ra_deg": obs.ra_deg,
                "dec_deg": obs.dec_deg,
                "observer_lat": obs.observer_lat,
                "observer_lon": obs.observer_lon,
                "telescope": obs.telescope,
                "detector": obs.detector,
                "focal_mm": obs.focal_mm,
                "aperture_mm": obs.aperture_mm,
                "pixel_um": obs.pixel_um,
                "frame_type": obs.frame_type,
            }.items() if v is not None
        }
    return body


def _camera_to_dict(cam) -> dict:
    return {
        "name": cam.name,
        "sensor_w_mm": cam.sensor_w_mm,
        "sensor_h_mm": cam.sensor_h_mm,
        "pixels_x": cam.pixels_x,
        "pixels_y": cam.pixels_y,
        "pixel_um": cam.pixel_um,
    }


def _optic_to_dict(optic) -> dict:
    return {
        "name": optic.name,
        "focal_mm": optic.focal_mm,
        "aperture_mm": optic.aperture_mm,
    }

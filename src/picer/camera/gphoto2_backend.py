"""Real camera backend using python-gphoto2 / libgphoto2."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import gphoto2 as gp

from picer.camera.models import (
    BulbProgress,
    CameraConfig,
    CaptureResult,
    ShutterSpeed,
)

logger = logging.getLogger(__name__)


class GPhoto2Backend:
    """Thread-safe libgphoto2 backend for Canon EOS cameras."""

    def __init__(self) -> None:
        self._camera: Optional[gp.Camera] = None
        self._lock = threading.Lock()
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            camera = gp.Camera()
            camera.init()
            self._camera = camera
            self._connected = True
            logger.info("Camera connected")

    def disconnect(self) -> None:
        with self._lock:
            if self._camera is not None:
                try:
                    self._camera.exit()
                except gp.GPhoto2Error:
                    pass
                self._camera = None
            self._connected = False
            logger.info("Camera disconnected")

    def is_connected(self) -> bool:
        return self._connected

    def list_cameras(self) -> list[str]:
        camera_list = gp.check_result(gp.gp_camera_autodetect())
        return [f"{name} at {addr}" for name, addr in camera_list]

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_config(self) -> CameraConfig:
        with self._lock:
            cfg = self._camera.get_config()

        shutter = ShutterSpeed.S_1
        iso = 400

        try:
            widget = cfg.get_child_by_name("shutterspeed")
            shutter = ShutterSpeed(widget.get_value())
        except (gp.GPhoto2Error, ValueError):
            pass

        try:
            widget = cfg.get_child_by_name("iso")
            iso = int(widget.get_value())
        except (gp.GPhoto2Error, ValueError):
            pass

        return CameraConfig(shutter_speed=shutter, iso=iso)

    def apply_config(self, config: CameraConfig) -> None:
        with self._lock:
            cfg = self._camera.get_config()

            try:
                w = cfg.get_child_by_name("shutterspeed")
                w.set_value(config.shutter_speed.value)
            except gp.GPhoto2Error as exc:
                logger.warning("Could not set shutter speed: %s", exc)

            try:
                w = cfg.get_child_by_name("iso")
                w.set_value(str(config.iso))
            except gp.GPhoto2Error as exc:
                logger.warning("Could not set ISO: %s", exc)

            try:
                w = cfg.get_child_by_name("imageformat")
                w.set_value(config.capture_format.value)
            except gp.GPhoto2Error as exc:
                logger.warning("Could not set image format: %s", exc)

            self._camera.set_config(cfg)

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture_single(
        self,
        config: CameraConfig,
        dest: Path,
        index: int = 0,
        on_progress: Optional[Callable[[BulbProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> CaptureResult:
        dest.mkdir(parents=True, exist_ok=True)
        self.apply_config(config)

        if config.shutter_speed == ShutterSpeed.BULB:
            return self._capture_bulb(config, dest, index, on_progress, cancel_check)
        return self._capture_with_retry(config, dest, index)

    def _capture_with_retry(
        self, config: CameraConfig, dest: Path, index: int, retries: int = 3
    ) -> CaptureResult:
        """Retry capture on transient I/O errors (e.g. [-110] I/O in progress)."""
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(retries):
            try:
                return self._capture_normal(config, dest, index)
            except gp.GPhoto2Error as exc:
                last_exc = exc
                if attempt < retries - 1:
                    wait = 1.0 * (attempt + 1)
                    logger.warning(
                        "Capture attempt %d/%d failed (%s) — retrying in %.1fs",
                        attempt + 1, retries, exc, wait,
                    )
                    time.sleep(wait)
        raise last_exc

    def _capture_normal(
        self, config: CameraConfig, dest: Path, index: int
    ) -> CaptureResult:
        with self._lock:
            t_start = time.time()
            file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
            camera_file = self._camera.file_get(
                file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL
            )
            out_path = dest / file_path.name
            camera_file.save(str(out_path))

        logger.info("Captured %s", out_path.name)
        return CaptureResult(
            frame_index=index,
            file_path=out_path,
            exposure_s=config.shutter_speed.to_seconds(),
            iso=config.iso,
            timestamp=t_start,
        )

    def _capture_bulb(
        self,
        config: CameraConfig,
        dest: Path,
        index: int,
        on_progress: Optional[Callable[[BulbProgress], None]],
        cancel_check: Optional[Callable[[], bool]],
    ) -> CaptureResult:
        duration = config.bulb_duration_s
        t_start = time.time()

        # Press shutter
        with self._lock:
            cfg = self._camera.get_config()
            release = cfg.get_child_by_name("eosremoterelease")
            release.set_value("Immediate")
            self._camera.set_config(cfg)

        logger.info("Bulb open for %.1fs", duration)

        # Hold — outside the lock so other threads (UI) can proceed
        interval = 0.5
        elapsed = 0.0
        while elapsed < duration:
            if cancel_check is not None and cancel_check():
                logger.info("Bulb exposure cancelled at %.1fs", elapsed)
                break
            sleep_time = min(interval, duration - elapsed)
            time.sleep(sleep_time)
            elapsed = time.monotonic() - (time.monotonic() - elapsed - sleep_time + elapsed)
            elapsed = time.time() - t_start
            if on_progress is not None:
                on_progress(BulbProgress(elapsed_s=elapsed, total_s=duration))

        # Release shutter
        with self._lock:
            cfg = self._camera.get_config()
            release = cfg.get_child_by_name("eosremoterelease")
            release.set_value("Release Full")
            self._camera.set_config(cfg)

        logger.info("Bulb closed, waiting for file")

        # Wait for the camera to send the file
        out_path: Optional[Path] = None
        with self._lock:
            deadline = time.time() + 15
            while time.time() < deadline:
                event_type, event_data = self._camera.wait_for_event(2000)
                if event_type == gp.GP_EVENT_FILE_ADDED:
                    camera_file = self._camera.file_get(
                        event_data.folder,
                        event_data.name,
                        gp.GP_FILE_TYPE_NORMAL,
                    )
                    out_path = dest / event_data.name
                    camera_file.save(str(out_path))
                    break

        if out_path is None:
            raise RuntimeError("Timed out waiting for bulb capture file from camera")

        logger.info("Bulb capture saved to %s", out_path.name)
        return CaptureResult(
            frame_index=index,
            file_path=out_path,
            exposure_s=duration,
            iso=config.iso,
            timestamp=t_start,
        )

    def set_config_widget(self, name: str, value: str) -> None:
        """Set an arbitrary gphoto2 config widget by name (for CLI power users)."""
        with self._lock:
            cfg = self._camera.get_config()
            widget = cfg.get_child_by_name(name)
            widget.set_value(value)
            self._camera.set_config(cfg)

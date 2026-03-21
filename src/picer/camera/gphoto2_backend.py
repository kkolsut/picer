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
            self._drain_events()
            logger.info("Camera connected")

    def _drain_events(self) -> None:
        """Consume pending camera events to clear any I/O-in-progress state.

        Must be called while holding self._lock.
        Canon cameras often queue events after init or after a capture;
        calling set_config while those are pending returns [-110].
        """
        for _ in range(30):
            try:
                event_type, _ = self._camera.wait_for_event(100)
                if event_type == gp.GP_EVENT_TIMEOUT:
                    break
            except gp.GPhoto2Error:
                break

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
            raw = widget.get_value()
            logger.debug("get_config: raw shutterspeed value from camera: %r", raw)
            shutter = ShutterSpeed(raw)
            logger.debug("get_config: parsed shutter speed: %s", shutter)
        except gp.GPhoto2Error as exc:
            logger.warning("get_config: could not read shutterspeed widget: %s", exc)
        except ValueError:
            logger.warning("get_config: unrecognised shutterspeed value %r — falling back to S_1", raw)

        try:
            widget = cfg.get_child_by_name("iso")
            iso = int(widget.get_value())
            logger.debug("get_config: raw iso value from camera: %r", iso)
        except (gp.GPhoto2Error, ValueError):
            pass

        result = CameraConfig(shutter_speed=shutter, iso=iso)
        logger.debug("get_config: returning %s", result)
        return result

    def _set_config_with_retry(
        self, cfg, retries: int = 5, delay: float = 1.0
    ) -> None:
        """Call set_config, retrying on transient [-110] I/O-in-progress errors.

        Must be called while holding self._lock.
        """
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(retries):
            try:
                self._camera.set_config(cfg)
                return
            except gp.GPhoto2Error as exc:
                last_exc = exc
                if attempt < retries - 1:
                    logger.warning(
                        "set_config attempt %d/%d failed (%s) — retrying in %.1fs",
                        attempt + 1, retries, exc, delay,
                    )
                    time.sleep(delay)
        raise last_exc

    def apply_config(self, config: CameraConfig) -> None:
        logger.debug("apply_config: requested shutter=%s iso=%s format=%s",
                     config.shutter_speed, config.iso, config.capture_format)
        with self._lock:
            cfg = self._camera.get_config()

            try:
                w = cfg.get_child_by_name("shutterspeed")
            except gp.GPhoto2Error:
                raise
            choices = list(w.get_choices()) if hasattr(w, "get_choices") else []
            logger.debug("apply_config: shutterspeed choices: %s", choices)
            desired = config.shutter_speed.value
            # Match case-insensitively (camera may report "bulb", enum has "Bulb")
            actual = next((c for c in choices if c.lower() == desired.lower()), None)
            if actual is None:
                raise ValueError(
                    f"Camera rejected shutter speed '{desired}' "
                    f"(available: {choices}). Switch the camera dial to M (Manual) mode."
                )
            logger.debug("apply_config: setting shutterspeed to %r", actual)
            w.set_value(actual)

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

            try:
                self._set_config_with_retry(cfg)
            except gp.GPhoto2Error as exc:
                logger.warning("apply_config: set_config failed after retries: %s", exc)

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

        if config.shutter_speed == ShutterSpeed.BULB:
            # Do NOT call apply_config before bulb: every set_config call on the
            # Canon 450D in bulb mode triggers a shutter release.  ISO/imageformat
            # are irrelevant for timing control; the bulb open/close are the only
            # two set_config calls we want to make.
            return self._capture_bulb(config, dest, index, on_progress, cancel_check)

        self.apply_config(config)
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
            self._drain_events()

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

        # Step 1: ensure shutterspeed is set to "bulb".
        # Done while the camera is still at a non-bulb speed so set_config is safe.
        # (On Canon EOS, set_config *while already in bulb mode* fires the shutter —
        # but transitioning INTO bulb mode is safe.)
        with self._lock:
            cfg = self._camera.get_config()
            try:
                ss_widget = cfg.get_child_by_name("shutterspeed")
                choices = list(ss_widget.get_choices())
                bulb_val = next((c for c in choices if c.lower() == "bulb"), None)
                if bulb_val is None:
                    raise ValueError(
                        f"Camera does not support Bulb mode (choices: {choices}). "
                        "Switch the camera dial to M and set shutter speed to Bulb, "
                        "or use the B (Bulb) dial position."
                    )
                if ss_widget.get_value().lower() != "bulb":
                    ss_widget.set_value(bulb_val)
                    self._camera.set_config(cfg)
            except gp.GPhoto2Error as exc:
                logger.warning("Could not set shutterspeed to bulb: %s", exc)

        # Step 2: press shutter — drain first, then send exactly once.
        # Only eosremoterelease changes here; shutterspeed is already "bulb".
        # Do NOT retry: each set_config("Press Full") fires the shutter.
        with self._lock:
            self._drain_events()
            cfg = self._camera.get_config()
            release = cfg.get_child_by_name("eosremoterelease")
            release.set_value("Press Full")
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
            elapsed = time.time() - t_start
            if on_progress is not None:
                on_progress(BulbProgress(elapsed_s=elapsed, total_s=duration))

        # Release shutter — retrying here is safe (doesn't re-fire, just closes).
        with self._lock:
            cfg = self._camera.get_config()
            release = cfg.get_child_by_name("eosremoterelease")
            release.set_value("Release Full")
            self._set_config_with_retry(cfg)

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
            self._set_config_with_retry(cfg)

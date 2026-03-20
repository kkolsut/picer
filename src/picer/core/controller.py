"""CameraController — high-level orchestrator used by both GUI and CLI."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from picer.camera.base import CameraBackend
from picer.camera.models import BulbProgress, CameraConfig, CaptureResult, FrameType, SequenceConfig
from picer.core.sequence import SequenceRunner
from picer.utils.gvfs_inhibit import ensure_camera_accessible

logger = logging.getLogger(__name__)


class CameraController:
    def __init__(self, backend: CameraBackend) -> None:
        self._backend = backend
        self._runner: Optional[SequenceRunner] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> tuple[bool, str]:
        """
        Connect to the camera after checking for GVFS conflicts.
        Returns (success, error_message).
        """
        ok, msg = ensure_camera_accessible()
        if not ok:
            return False, msg

        try:
            self._backend.connect()
            return True, ""
        except Exception as exc:
            logger.error("Failed to connect: %s", exc)
            return False, str(exc)

    def disconnect(self) -> None:
        self._backend.disconnect()

    def is_connected(self) -> bool:
        return self._backend.is_connected()

    def list_cameras(self) -> list[str]:
        return self._backend.list_cameras()

    # ------------------------------------------------------------------
    # Single capture
    # ------------------------------------------------------------------

    def capture(
        self,
        config: CameraConfig,
        output_dir: Path,
        filename_template: str = "{type}_{date}_{seq:04d}",
        frame_type: FrameType = FrameType.LIGHT,
        on_progress: Optional[Callable[[BulbProgress], None]] = None,
    ) -> CaptureResult:
        seq_cfg = SequenceConfig(
            frame_count=1,
            output_dir=output_dir,
            filename_template=filename_template,
            frame_type=frame_type,
            camera_config=config,
        )
        runner = SequenceRunner(backend=self._backend, config=seq_cfg, on_bulb_progress=on_progress)
        results = runner.run_blocking()
        if not results:
            raise RuntimeError("Capture produced no result")
        return results[0]

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    def start_sequence(
        self,
        config: SequenceConfig,
        on_frame_start: Optional[Callable[[int, int], None]] = None,
        on_frame_complete: Optional[Callable[[CaptureResult], None]] = None,
        on_bulb_progress: Optional[Callable[[BulbProgress], None]] = None,
        on_error: Optional[Callable[[int, Exception], bool]] = None,
        on_sequence_complete: Optional[Callable[[list[CaptureResult]], None]] = None,
        on_fits_ready: Optional[Callable] = None,
    ) -> None:
        with self._lock:
            if self._runner and self._runner.is_running():
                raise RuntimeError("A sequence is already running")
            self._runner = SequenceRunner(
                backend=self._backend,
                config=config,
                on_frame_start=on_frame_start,
                on_frame_complete=on_frame_complete,
                on_bulb_progress=on_bulb_progress,
                on_error=on_error,
                on_sequence_complete=on_sequence_complete,
                on_fits_ready=on_fits_ready,
            )
            self._runner.start()

    def stop_sequence(self) -> None:
        with self._lock:
            if self._runner:
                self._runner.cancel()

    def is_sequence_running(self) -> bool:
        with self._lock:
            return self._runner is not None and self._runner.is_running()

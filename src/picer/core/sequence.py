"""SequenceRunner — drives multi-frame capture loops."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from picer.camera.base import CameraBackend
from picer.camera.models import BulbProgress, CaptureResult, SequenceConfig
from picer.utils.file_naming import build_output_path, find_next_seq

logger = logging.getLogger(__name__)


class SequenceRunner:
    """
    Runs a sequence of captures in a background thread.

    interval_s is start-to-start: the next frame begins `interval_s` seconds
    after the current frame started. If the exposure takes longer than
    interval_s, the next frame starts immediately.
    """

    def __init__(
        self,
        backend: CameraBackend,
        config: SequenceConfig,
        on_frame_start: Optional[Callable[[int, int], None]] = None,
        on_frame_complete: Optional[Callable[[CaptureResult], None]] = None,
        on_bulb_progress: Optional[Callable[[BulbProgress], None]] = None,
        on_error: Optional[Callable[[int, Exception], bool]] = None,
        on_sequence_complete: Optional[Callable[[list[CaptureResult]], None]] = None,
        on_fits_ready: Optional[Callable] = None,
    ) -> None:
        self._backend = backend
        self._config = config
        self._on_frame_start = on_frame_start
        self._on_frame_complete = on_frame_complete
        self._on_bulb_progress = on_bulb_progress
        self._on_error = on_error          # return True=continue, False=abort
        self._on_sequence_complete = on_sequence_complete
        self._on_fits_ready = on_fits_ready
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the sequence in a background thread."""
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def run_blocking(self) -> list[CaptureResult]:
        """Run the sequence in the calling thread and return results."""
        return self._run()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> list[CaptureResult]:
        cfg = self._config
        results: list[CaptureResult] = []

        cfg.output_dir.mkdir(parents=True, exist_ok=True)

        seq_start = find_next_seq(
            cfg.output_dir,
            cfg.filename_template,
            cfg.camera_config.capture_format.extension,
            cfg.frame_type,
        )
        if seq_start > 1:
            logger.info("Existing files detected; starting sequence at seq=%d", seq_start)

        for idx in range(cfg.frame_count):
            if self._cancel_event.is_set():
                logger.info("Sequence cancelled before frame %d", idx)
                break

            t_frame_start = time.monotonic()

            if self._on_frame_start:
                self._on_frame_start(idx, cfg.frame_count)

            dest = build_output_path(
                cfg.output_dir,
                cfg.filename_template,
                cfg.camera_config,
                seq=seq_start + idx,
                frame_type=cfg.frame_type,
            ).parent

            try:
                result = self._backend.capture_single(
                    config=cfg.camera_config,
                    dest=dest,
                    index=idx,
                    on_progress=self._on_bulb_progress,
                    cancel_check=self._cancel_event.is_set,
                )
                # Rename to match the template
                desired_path = build_output_path(
                    cfg.output_dir,
                    cfg.filename_template,
                    cfg.camera_config,
                    seq=seq_start + idx,
                    frame_type=cfg.frame_type,
                )
                if result.file_path != desired_path:
                    desired_path.parent.mkdir(parents=True, exist_ok=True)
                    result.file_path.rename(desired_path)
                    result = CaptureResult(
                        frame_index=result.frame_index,
                        file_path=desired_path,
                        exposure_s=result.exposure_s,
                        iso=result.iso,
                        timestamp=result.timestamp,
                    )

                results.append(result)
                logger.info(
                    "Frame %d/%d → %s", idx + 1, cfg.frame_count, result.file_path.name
                )

                if self._on_frame_complete:
                    self._on_frame_complete(result)

                if result.file_path.suffix.lower() == ".cr2" and self._on_fits_ready:
                    _result = result
                    _cb = self._on_fits_ready

                    def _do_convert() -> None:
                        try:
                            from picer.utils.fits_converter import cr2_to_fits
                            paths = cr2_to_fits(_result.file_path)
                            _cb(_result, paths)
                        except Exception as exc:
                            logger.warning("FITS conversion failed: %s", exc)

                    threading.Thread(target=_do_convert, daemon=True).start()

            except Exception as exc:
                logger.error("Frame %d failed: %s", idx, exc)
                if self._on_error:
                    should_continue = self._on_error(idx, exc)
                    if not should_continue:
                        break
                # Default: continue on error

            # Wait for start-to-start interval
            if cfg.interval_s > 0 and idx < cfg.frame_count - 1:
                elapsed = time.monotonic() - t_frame_start
                wait = cfg.interval_s - elapsed
                if wait > 0:
                    self._cancel_event.wait(timeout=wait)

        if self._on_sequence_complete:
            self._on_sequence_complete(results)

        return results

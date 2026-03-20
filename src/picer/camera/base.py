from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

from picer.camera.models import BulbProgress, CameraConfig, CaptureResult


@runtime_checkable
class CameraBackend(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def list_cameras(self) -> list[str]: ...
    def get_config(self) -> CameraConfig: ...
    def apply_config(self, config: CameraConfig) -> None: ...
    def capture_single(
        self,
        config: CameraConfig,
        dest: Path,
        index: int = 0,
        on_progress: Optional[Callable[[BulbProgress], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> CaptureResult: ...

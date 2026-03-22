"""In-memory registry of captures produced during the current server session."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from picer.camera.models import CaptureResult


@dataclass
class CaptureRecord:
    id: str
    result: CaptureResult
    fits_paths: dict[str, Path] = field(default_factory=dict)


class CaptureRegistry:
    def __init__(self) -> None:
        self._records: dict[str, CaptureRecord] = {}

    def add(self, result: CaptureResult) -> str:
        capture_id = str(uuid.uuid4())
        self._records[capture_id] = CaptureRecord(id=capture_id, result=result)
        return capture_id

    def get(self, capture_id: str) -> Optional[CaptureRecord]:
        return self._records.get(capture_id)

    def all(self) -> list[CaptureRecord]:
        return list(self._records.values())

    def delete(self, capture_id: str) -> bool:
        if capture_id not in self._records:
            return False
        del self._records[capture_id]
        return True

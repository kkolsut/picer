from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class FrameType(Enum):
    LIGHT = "light"
    DARK = "dark"
    FLAT = "flat"
    BIAS = "bias"

    @property
    def label(self) -> str:
        return self.value.capitalize()


class CaptureFormat(Enum):
    RAW = "RAW"
    JPEG = "Large Fine JPEG"
    RAW_JPEG = "RAW + Large Fine JPEG"

    @property
    def extension(self) -> str:
        if self == CaptureFormat.JPEG:
            return ".jpg"
        return ".cr2"

    @property
    def label(self) -> str:
        return {
            CaptureFormat.RAW: "RAW (.cr2)",
            CaptureFormat.JPEG: "JPEG",
            CaptureFormat.RAW_JPEG: "RAW + JPEG",
        }[self]


class ShutterSpeed(Enum):
    S_1_4000 = "1/4000"
    S_1_2000 = "1/2000"
    S_1_1000 = "1/1000"
    S_1_500 = "1/500"
    S_1_250 = "1/250"
    S_1_125 = "1/125"
    S_1_60 = "1/60"
    S_1_30 = "1/30"
    S_1_15 = "1/15"
    S_1_8 = "1/8"
    S_1_4 = "1/4"
    S_1_2 = "1/2"
    S_1 = "1"
    S_2 = "2"
    S_4 = "4"
    S_8 = "8"
    S_15 = "15"
    S_30 = "30"
    BULB = "Bulb"

    def to_seconds(self) -> float:
        if self == ShutterSpeed.BULB:
            return float("inf")
        val = self.value
        if "/" in val:
            num, den = val.split("/")
            return float(num) / float(den)
        return float(val)

    @classmethod
    def from_seconds(cls, seconds: float) -> ShutterSpeed:
        """Return BULB for >30s, otherwise the closest standard speed."""
        if seconds > 30:
            return cls.BULB
        non_bulb = [s for s in cls if s != cls.BULB]
        return min(non_bulb, key=lambda s: abs(s.to_seconds() - seconds))


ISO_VALUES = [100, 200, 400, 800, 1600]


@dataclass
class CameraConfig:
    shutter_speed: ShutterSpeed = ShutterSpeed.S_1
    iso: int = 400
    capture_format: CaptureFormat = CaptureFormat.RAW
    bulb_duration_s: float = 60.0  # used only when shutter_speed == BULB

    @property
    def effective_exposure_s(self) -> float:
        if self.shutter_speed == ShutterSpeed.BULB:
            return self.bulb_duration_s
        return self.shutter_speed.to_seconds()


@dataclass
class BulbProgress:
    elapsed_s: float
    total_s: float

    @property
    def percent(self) -> float:
        if self.total_s <= 0:
            return 100.0
        return min(100.0, self.elapsed_s / self.total_s * 100.0)

    @property
    def remaining_s(self) -> float:
        return max(0.0, self.total_s - self.elapsed_s)


@dataclass
class CaptureResult:
    frame_index: int
    file_path: Path
    exposure_s: float
    iso: int
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None


@dataclass
class SequenceConfig:
    frame_count: int = 1
    interval_s: float = 0.0  # start-to-start; 0 means back-to-back
    output_dir: Path = field(default_factory=lambda: Path.home() / "picer_captures")
    filename_template: str = "{type}_{date}_{seq:04d}"
    frame_type: FrameType = FrameType.LIGHT
    camera_config: CameraConfig = field(default_factory=CameraConfig)
    observation: Optional["ObservationMetadata"] = None


@dataclass
class ObservationMetadata:
    """Astronomical context collected at sequence-start time."""
    object_name:  Optional[str]   = None  # e.g. "M 42 — Orion Nebula"
    ra_deg:       Optional[float] = None  # J2000 decimal degrees
    dec_deg:      Optional[float] = None
    observer_lat: Optional[float] = None
    observer_lon: Optional[float] = None
    telescope:    Optional[str]   = None  # optic name
    detector:     Optional[str]   = None  # camera name
    focal_mm:     Optional[float] = None
    aperture_mm:  Optional[float] = None
    pixel_um:     Optional[float] = None
    frame_type:   Optional[str]   = None  # "object", "dark", "flat", "bias"

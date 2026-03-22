"""Gear data models for camera and optic (telescope/lens)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GearCamera:
    name: str
    sensor_w_mm: float
    sensor_h_mm: float
    pixels_x: int
    pixels_y: int
    pixel_um: float
    custom: bool = False


@dataclass
class GearOptic:
    name: str
    focal_mm: float
    aperture_mm: float
    custom: bool = False

    @property
    def f_ratio(self) -> float:
        return self.focal_mm / self.aperture_mm

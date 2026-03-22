"""Built-in catalog of common astrophotography cameras and optics."""
from __future__ import annotations

from picer.gear.models import GearCamera, GearOptic

CAMERAS: list[GearCamera] = [
    GearCamera("Canon EOS 350D", 22.2, 14.8, 3456, 2304, 6.42),
    GearCamera("Canon EOS 400D", 22.2, 14.8, 3888, 2592, 5.72),
    GearCamera("Canon EOS 450D", 22.2, 14.8, 4272, 2848, 5.19),
    GearCamera("Canon EOS 500D", 22.3, 14.9, 4752, 3168, 4.69),
    GearCamera("Canon EOS 550D", 22.3, 14.9, 5184, 3456, 4.30),
    GearCamera("Canon EOS 600D", 22.3, 14.9, 5184, 3456, 4.30),
    GearCamera("Canon EOS 700D", 22.3, 14.9, 5184, 3456, 4.30),
    GearCamera("Canon EOS 1100D", 22.2, 14.7, 4272, 2848, 5.19),
    GearCamera("Canon EOS 1200D", 22.3, 14.9, 5184, 3456, 4.29),
    GearCamera("Canon EOS 6D", 35.8, 23.9, 5472, 3648, 6.54),
    GearCamera("Canon EOS 6D Mark II", 35.9, 24.0, 6240, 4160, 5.74),
    GearCamera("Canon EOS 7D", 22.3, 14.9, 5184, 3456, 4.30),
    GearCamera("Canon EOS 7D Mark II", 22.4, 15.0, 5472, 3648, 4.09),
    GearCamera("Nikon D3200", 23.2, 15.4, 6016, 4000, 3.91),
    GearCamera("Nikon D5300", 23.5, 15.6, 6000, 4000, 3.92),
    GearCamera("Nikon D7100", 23.5, 15.6, 6000, 4000, 3.92),
    GearCamera("Sony A7 III", 35.6, 23.8, 6000, 4000, 5.96),
]

OPTICS: list[GearOptic] = [
    # Telescopes
    GearOptic("Sky-Watcher 80ED", 600.0, 80.0),
    GearOptic("Sky-Watcher 100ED", 900.0, 100.0),
    GearOptic("Sky-Watcher Esprit 80", 400.0, 80.0),
    GearOptic("Sky-Watcher Esprit 100", 550.0, 100.0),
    GearOptic("Sky-Watcher Esprit 120", 840.0, 120.0),
    GearOptic("Celestron C8 SCT", 2032.0, 203.0),
    GearOptic("Celestron C11 SCT", 2800.0, 279.0),
    GearOptic("Takahashi FSQ-85", 450.0, 85.0),
    GearOptic("Takahashi FSQ-106", 530.0, 106.0),
    GearOptic("William Optics GT81", 382.0, 81.0),
    GearOptic("William Optics RedCat 51", 250.0, 51.0),
    GearOptic("Meade 6\" ACF", 1524.0, 152.0),
    # Canon-compatible lenses
    GearOptic("Canon EF 50mm f/1.4 USM", 50.0, 35.7),
    GearOptic("Canon EF 50mm f/1.8 STM", 50.0, 27.8),
    GearOptic("Canon EF 85mm f/1.8 USM", 85.0, 47.2),
    GearOptic("Canon EF 135mm f/2.0L", 135.0, 67.5),
    GearOptic("Canon EF 200mm f/2.8L II", 200.0, 71.4),
    GearOptic("Canon EF 300mm f/4L IS", 300.0, 75.0),
    GearOptic("Canon EF 400mm f/5.6L", 400.0, 71.4),
    GearOptic("Sigma 14mm f/1.8 Art", 14.0, 7.8),
    GearOptic("Sigma 50mm f/1.4 Art", 50.0, 35.7),
    GearOptic("Rokinon 135mm f/2.0", 135.0, 67.5),
    GearOptic("Canon EF 70-200mm f/2.8L (200mm)", 200.0, 71.4),
]

# Gear Selection Feature (Camera + Telescope/Lens)

## Context

Picer currently has no concept of the user's optical setup. Adding a gear selector lets the
app display field-of-view, plate scale, and other derived values for the selected
camera+optic pair. Users need both a pre-defined catalog of common amateur-astronomy gear
and the ability to add their own custom entries. Settings must persist across sessions.

## Storage: JSON at `~/.config/picer/gear.json`

**Why JSON:**
- Zero new dependencies (built-in `json` + `pathlib`)
- Human-editable for power users
- Simple to append user additions without touching the built-in catalog
- Fits the project's existing "no persistence" gap cleanly

**File location:** `~/.config/picer/gear.json` (XDG-compliant)

**Schema:**
```json
{
  "cameras": [
    {"name": "My Canon 600D", "sensor_w_mm": 22.3, "sensor_h_mm": 14.9,
     "pixels_x": 5184, "pixels_y": 3456, "pixel_um": 4.30, "custom": true}
  ],
  "optics": [
    {"name": "My 80ED", "focal_mm": 600, "aperture_mm": 80, "custom": true}
  ],
  "selected_camera": "My Canon 600D",
  "selected_optic": "My 80ED"
}
```

Built-in catalog entries are shipped as Python constants (not in the JSON file).
The JSON file stores **only user additions and the current selection**.
On load: merge built-in catalog + user custom entries.

---

## New files

### `src/picer/gear/__init__.py` — empty

### `src/picer/gear/models.py`
```python
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
    def f_ratio(self) -> float: return self.focal_mm / self.aperture_mm
```

### `src/picer/gear/catalog.py`
Built-in lists of `GearCamera` and `GearOptic`. Key entries:

**Cameras (common DSLRs for astrophotography):**
| Name | W×H mm | Pixels | µm |
|---|---|---|---|
| Canon EOS 350D | 22.2×14.8 | 3456×2304 | 6.42 |
| Canon EOS 400D | 22.2×14.8 | 3888×2592 | 5.72 |
| Canon EOS 450D | 22.2×14.8 | 4272×2848 | 5.19 |
| Canon EOS 500D | 22.3×14.9 | 4752×3168 | 4.69 |
| Canon EOS 550D | 22.3×14.9 | 5184×3456 | 4.30 |
| Canon EOS 600D | 22.3×14.9 | 5184×3456 | 4.30 |
| Canon EOS 700D | 22.3×14.9 | 5184×3456 | 4.30 |
| Canon EOS 1100D | 22.2×14.7 | 4272×2848 | 5.19 |
| Canon EOS 1200D | 22.3×14.9 | 5184×3456 | 4.29 |
| Canon EOS 6D | 35.8×23.9 | 5472×3648 | 6.54 |
| Canon EOS 6D Mark II | 35.9×24.0 | 6240×4160 | 5.74 |
| Canon EOS 7D | 22.3×14.9 | 5184×3456 | 4.30 |
| Canon EOS 7D Mark II | 22.4×15.0 | 5472×3648 | 4.09 |
| Nikon D3200 | 23.2×15.4 | 6016×4000 | 3.91 |
| Nikon D5300 | 23.5×15.6 | 6000×4000 | 3.92 |
| Nikon D7100 | 23.5×15.6 | 6000×4000 | 3.92 |
| Sony A7 III | 35.6×23.8 | 6000×4000 | 5.96 |

**Optics — Telescopes:**
| Name | Focal mm | Aperture mm |
|---|---|---|
| Sky-Watcher 80ED | 600 | 80 |
| Sky-Watcher 100ED | 900 | 100 |
| Sky-Watcher Esprit 80 | 400 | 80 |
| Sky-Watcher Esprit 100 | 550 | 100 |
| Sky-Watcher Esprit 120 | 840 | 120 |
| Celestron C8 SCT | 2032 | 203 |
| Celestron C11 SCT | 2800 | 279 |
| Takahashi FSQ-85 | 450 | 85 |
| Takahashi FSQ-106 | 530 | 106 |
| William Optics GT81 | 382 | 81 |
| William Optics RedCat 51 | 250 | 51 |
| Meade 6" ACF | 1524 | 152 |

**Optics — Canon-compatible lenses:**
| Name | Focal mm | Aperture mm |
|---|---|---|
| Canon EF 50mm f/1.4 USM | 50 | 35.7 |
| Canon EF 50mm f/1.8 STM | 50 | 27.8 |
| Canon EF 85mm f/1.8 USM | 85 | 47.2 |
| Canon EF 135mm f/2.0L | 135 | 67.5 |
| Canon EF 200mm f/2.8L II | 200 | 71.4 |
| Canon EF 300mm f/4L IS | 300 | 75.0 |
| Canon EF 400mm f/5.6L | 400 | 71.4 |
| Sigma 14mm f/1.8 Art | 14 | 7.8 |
| Sigma 50mm f/1.4 Art | 50 | 35.7 |
| Rokinon 135mm f/2.0 | 135 | 67.5 |
| Canon EF 70-200mm f/2.8L (@ 200mm) | 200 | 71.4 |

### `src/picer/gear/store.py`
```python
CONFIG_PATH = Path.home() / ".config" / "picer" / "gear.json"

def load_gear() -> tuple[list[GearCamera], list[GearOptic], str | None, str | None]:
    """Returns (cameras, optics, selected_camera_name, selected_optic_name).
    Merges built-in catalog with user custom entries from JSON."""

def save_user_gear(
    custom_cameras: list[GearCamera],
    custom_optics: list[GearOptic],
    selected_camera: str | None,
    selected_optic: str | None,
) -> None:
    """Writes only user additions + selection to JSON (never overwrites catalog)."""

def add_custom_camera(cam: GearCamera) -> None: ...
def add_custom_optic(optic: GearOptic) -> None: ...
```

---

## Modified files

### `src/picer/gui/panels/gear_panel.py` — new panel
```
┌─ Gear ──────────────────────────────────┐
│ Camera:  [Canon EOS 450D          ▾] [+]│
│          22.2×14.8 mm · 5.19 µm        │
│ Optic:   [Sky-Watcher 80ED        ▾] [+]│
│          600 mm f/7.5                   │
│ FOV: 2.1° × 1.4°  ·  Plate: 1.83"/px   │
└─────────────────────────────────────────┘
```
- Two `ComboBoxText` dropdowns (camera, optic) with `[+]` buttons
- Info row below each showing key specs
- FOV + plate scale line computed from selection
- On change: calls `store.save_user_gear(...)` to persist selection
- `[+]` opens `AddGearDialog`

### `src/picer/gui/dialogs/add_gear_dialog.py` — new
Simple `Gtk.Window` (modal) with fields:
- **Camera:** Name, sensor W mm, sensor H mm, pixels X, pixels Y, pixel µm
- **Optic:** Name, focal length mm, aperture mm
Submit → calls `store.add_custom_camera()` / `store.add_custom_optic()`, refreshes dropdown

### `src/picer/gui/main_window.py` — add GearPanel to left sidebar
```python
from picer.gui.panels.gear_panel import GearPanel
self._gear_panel = GearPanel()
left_box.append(self._gear_panel)   # insert at top, above exposure_panel
```

---

## FOV & plate scale formulas

```python
import math
fov_w_deg = 2 * math.degrees(math.atan(sensor_w_mm / (2 * focal_mm)))
fov_h_deg = 2 * math.degrees(math.atan(sensor_h_mm / (2 * focal_mm)))
plate_scale_arcsec_per_px = 206.265 * pixel_um / focal_mm
```

---

## Verification

1. Launch app → Gear panel appears at top of left sidebar with both dropdowns populated
2. Select a camera → info row shows sensor size + pixel size; FOV line updates
3. Select an optic → FOV + plate scale line updates
4. Click `[+]` on Camera → dialog opens, fill fields, submit → appears in dropdown, selected
5. Quit and relaunch → custom entry and selection are restored from `~/.config/picer/gear.json`
6. `~/.config/picer/gear.json` contains only custom entries + selection (no built-in catalog duplication)

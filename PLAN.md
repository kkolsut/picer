# Picer — Astronomy DSLR Capture App (Canon EOS 450D)

## Context
User wants a Linux app to control a Canon EOS 450D (Rebel XSi) over USB for astrophotography. Critical need: set long exposure times (including bulb mode for >30s). Needs both a GTK4 GUI and a CLI for scripting pipelines. `libgphoto2` 2.5.33 is already installed; the CLI tool, dev headers, and Python bindings are not yet installed.

---

## Technology Stack
- **Camera control**: `python-gphoto2` (Python bindings for libgphoto2)
- **GUI**: GTK4 + libadwaita via `PyGObject` (already installed system-wide on Fedora 43)
- **CLI**: `click` with `rich` for progress output
- **Config/models**: `pydantic` dataclasses
- **Testing**: `pytest` with mock camera backend

---

## Project Structure

```
picer/
├── pyproject.toml
├── udev/
│   └── 99-picer-camera.rules      # prevent GVFS from claiming camera
├── src/picer/
│   ├── __init__.py
│   ├── __main__.py
│   ├── camera/
│   │   ├── models.py              # CameraConfig, CaptureResult, SequenceConfig dataclasses
│   │   ├── base.py                # CameraBackend Protocol (abstract interface)
│   │   ├── gphoto2_backend.py     # Real implementation via python-gphoto2
│   │   └── mock_backend.py        # Simulation backend for dev/testing without hardware
│   ├── core/
│   │   ├── controller.py          # CameraController: orchestrates, handles threading
│   │   ├── bulb.py                # BulbExposure: shutter press/hold/release + progress
│   │   └── sequence.py            # SequenceRunner: multi-frame capture loop
│   ├── gui/
│   │   ├── app.py                 # Gtk.Application subclass
│   │   ├── main_window.py         # AdwApplicationWindow, panel layout
│   │   └── panels/
│   │       ├── exposure_panel.py  # Shutter speed dropdown + bulb duration spinner
│   │       ├── iso_panel.py       # ISO dropdown (100/200/400/800/1600)
│   │       ├── sequence_panel.py  # Frame count, interval, progress bar, start/stop
│   │       ├── format_panel.py    # File format dropdown: RAW / JPEG / RAW+JPEG
│   │       ├── output_panel.py    # Save dir, filename template
│   │       └── preview_panel.py   # Thumbnail of last capture + histogram placeholder
│   ├── cli/
│   │   └── commands.py            # Click CLI: capture, sequence, info, config subcommands
│   └── utils/
│       ├── gvfs_inhibit.py        # Detect/unmount GVFS camera mount
│       └── file_naming.py         # Template engine: {date}, {seq:04d}, {iso}, {exp}
└── tests/
    ├── conftest.py                 # pytest fixtures, mock backend
    ├── test_bulb.py
    ├── test_sequence.py
    ├── test_file_naming.py
    └── test_cli.py
```

---

## Key Implementation Details

### pyproject.toml dependencies
```toml
dependencies = [
    "gphoto2>=2.5.0",       # python-gphoto2 C bindings (needs libgphoto2-devel to build)
    "PyGObject>=3.44.0",    # system package, use --system-site-packages venv
    "click>=8.1",
    "rich>=13.0",
    "pydantic>=2.0",
]
[project.scripts]
picer     = "picer.cli.commands:main"
picer-gui = "picer.gui.app:main"
```

### GVFS Conflict (critical first-time setup)
`gvfs-gphoto2` auto-mounts the camera, blocking libgphoto2. Two-pronged fix:
1. **udev rule** (permanent): `ENV{GVFS_IGNORE}="1"` for Canon 450D VID `04a9` PID `317c`
2. **Runtime guard**: `gvfs_inhibit.py` detects and calls `gio mount --unmount gphoto2://` at startup

### Bulb Mode (exposures > 30s) — `src/picer/core/bulb.py`
Uses the `eosremoterelease` gphoto2 config widget on the 450D:
1. Set `shutterspeed` widget to `"Bulb"`
2. Set `eosremoterelease` → `"Immediate"` (shutter open, hold lock only for this call)
3. **Sleep outside the lock** for `duration_s` (keeps UI responsive)
4. Set `eosremoterelease` → `"Release Full"` (shutter close)
5. `camera.wait_for_event()` until `GP_EVENT_FILE_ADDED`
6. Download file

`BulbProgress` callbacks report elapsed/total every 0.5s → feeds GUI progress bar and CLI rich progress.

### Threading Model (GTK4)
All gphoto2 calls run in background `threading.Thread` (daemon). Results posted to GTK main thread via `GLib.idle_add()`. Never call GTK from worker thread. A `threading.Lock` serializes all camera calls.

### Sequence Capture — `src/picer/core/sequence.py`
- `interval_s` = start-to-start (not gap between frames, consistent with APT/SGP convention)
- Callbacks: `on_frame_start`, `on_frame_complete`, `on_bulb_progress`, `on_error`
- `on_error` returns `bool`: `True` = continue, `False` = abort sequence
- Cancellable via `threading.Event`

### CLI Commands
```
picer info                              # detect cameras, show GVFS status
picer capture --exposure 120 --iso 800 --format raw --output ~/captures
picer sequence --frames 30 --exposure 180 --iso 1600 --interval 5 --output ~/captures/m31
picer config set shutterspeed "1/250"   # raw widget access for debugging
picer gui                               # launch GUI
```

### GUI Layout
```
AdwApplicationWindow
├── AdwHeaderBar [Connect button | Status dot]
└── GtkPaned (horizontal)
    ├── Left panel (settings):
    │   ├── ExposurePanel  — dropdown (1/4000…30…BULB) + bulb duration spinner
    │   ├── ISOPanel       — dropdown
    │   ├── FormatPanel    — GtkDropDown: RAW (.cr2) | JPEG | RAW + JPEG
    │   ├── SequencePanel  — frame count, interval, progress, start/stop
    │   └── OutputPanel    — dir picker, filename template
    └── Right panel:
        └── PreviewPanel   — last frame thumbnail + histogram (GtkDrawingArea)
```

**FormatPanel** (`src/picer/gui/panels/format_panel.py`):
- `GtkDropDown` with three options: `RAW (.cr2)`, `Large Fine JPEG`, `RAW + Large Fine JPEG`
- Default: `RAW (.cr2)` (correct default for astronomy — never shoot JPEG-only)
- Changing format immediately calls `apply_config()` on the camera (if connected)
- Selection is persisted to app settings between sessions

### File Naming Templates
Tokens: `{date}`, `{time}`, `{datetime}`, `{seq:04d}`, `{iso}`, `{exp}`, `{camera}`
Extension auto-appended from format (`.cr2` for RAW).

---

## Setup Sequence (to run before first use)
```bash
sudo dnf install libgphoto2-devel gphoto2 python3-devel
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
sudo cp udev/99-picer-camera.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
# unplug and replug camera; set camera to PTP mode (not Mass Storage)
picer info   # verify detection
```

---

## Verification
1. `picer info` → shows `Canon EOS 450D` detected, GVFS not blocking
2. `picer capture --exposure 5 --iso 400 --output /tmp/test` → single frame saved as `.cr2`
3. `picer capture --exposure 60 --iso 800 --output /tmp/test` → bulb mode, progress shown
4. `picer sequence --frames 3 --exposure 10 --interval 15 --output /tmp/seq` → 3 files saved
5. `picer-gui` → window opens, connect camera, run sequence via GUI
6. `pytest` → all tests pass using mock backend (no camera needed)

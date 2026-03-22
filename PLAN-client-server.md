# Effort Estimate: Picer → Server-Client Architecture

> **Status:** Reference document — no implementation yet. Standalone app continues as-is.
> **Last reviewed:** 2026-03-22

---

## What exists today

**~5,400 LOC across 8 packages** (was ~3,800 at original writing)

| Module | LOC | Notes |
|--------|-----|-------|
| `camera/` | 602 | `ObservationMetadata` dataclass added; `SequenceConfig.observation` field |
| `core/` | 349 | Unchanged structure; `on_fits_ready` callback added to `SequenceRunner` |
| `gui/` | 2,503 | +907 LOC: new `object_panel.py` (590), `preview_panel.py` (476), `add_gear_dialog.py` (147) |
| `gear/` | 222 | Minor: `update_custom_camera/optic` added to store |
| `objects/` | 685 | **NEW** — full DSO catalog (M, C, NGC, IC, B, LDN, LBN, Abell, UGC, PGC) + observer location store |
| `utils/` | 652 | `fits_converter.py` now writes 25+ FITS headers; new `gvfs_inhibit.py` (90 LOC) |
| `cli/` | 365 | Unchanged |

`CameraController` (`core/controller.py`) is already a clean boundary between hardware and UI — it maps almost directly to an HTTP API surface.

---

## Key architectural constraint

libgphoto2 requires direct USB access. The **API server must run on the machine the camera is physically plugged into** — it is a local daemon, not a hosted service. Desktop and web clients connect over LAN.

---

## Target architecture

```
Camera (USB)
     │
     ▼
┌─────────────────────────────────┐
│  Python API Server (FastAPI)    │  ← camera machine
│  REST + WebSocket               │
└──────────────┬──────────────────┘
               │  HTTP + WS (LAN, Basic Auth)
       ┌───────┴────────┐
       │                │
       ▼                ▼
 Python GTK4       Rails 8.1.2
 Desktop Client    Web Client
 (refactored)      (new, separate machine)
```

---

## Phase 1 — Python API Server (3–4 weeks)

**Stack:** FastAPI (async, built-in WebSocket, auto OpenAPI docs)

### What moves to the server

- `camera/` + `core/` — logic unchanged, wrapped in HTTP handlers
- `gear/store.py` — server-side JSON/SQLite persistence
- `objects/catalog.py`, `objects/store.py` — DSO catalog search + observer location persistence *(new)*
- `utils/fits_converter.py`, `utils/psf.py`, `utils/file_naming.py`, `utils/gvfs_inhibit.py`
- Captured files stored on the server machine; clients download on demand

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/cameras` | List detected cameras via gphoto2 |
| POST | `/connect` | Acquire session; returns 409 if already taken |
| DELETE | `/connect` | Release session |
| GET | `/status` | Connection state, free disk space warning |
| POST | `/capture` | Single frame → `CaptureResult` JSON |
| GET | `/captures/{id}/raw` | Download original RAW file |
| GET | `/captures/{id}/preview.jpg` | Server-rendered JPEG (for web preview) |
| DELETE | `/captures/{id}` | Delete a capture (manual only) |
| GET | `/captures/{id}/psf` | PSF/FWHM result JSON |
| POST | `/sequence` | Start sequence → session ID; body includes `observation` field *(updated)* |
| DELETE | `/sequence` | Stop sequence |
| WS | `/sequence/progress` | Frame/bulb progress + `fits_ready` event *(updated)* |
| GET/POST/PATCH/DELETE | `/gear/cameras` | Camera catalog CRUD |
| GET/POST/PATCH/DELETE | `/gear/optics` | Optic catalog CRUD |
| GET/PUT | `/gear/selection` | Active camera + optic |
| GET | `/objects/catalogs` | List catalog keys + labels *(new)* |
| GET | `/objects/search?catalog=NGC&q=1952` | Search a catalog → DSO JSON *(new)* |
| GET/PUT | `/objects/selection` | Get/set selected object *(new)* |
| GET/PUT | `/objects/location` | Get/set observer lat/lon *(new)* |
| GET/POST/DELETE | `/objects/favorites` | Location favorites CRUD *(new)* |

#### POST /sequence body (updated)

```json
{
  "frame_count": 10, "interval_s": 0, "frame_type": "object",
  "camera_config": { "shutter_speed": "120", "iso": 800, "capture_format": "RAW" },
  "observation": {
    "object_name": "NGC 1952", "ra_deg": 83.633, "dec_deg": 22.014,
    "observer_lat": 52.23, "observer_lon": 21.01,
    "telescope": "Sky-Watcher 80ED", "detector": "Canon EOS 450D",
    "focal_mm": 600.0, "aperture_mm": 80.0, "pixel_um": 5.19,
    "frame_type": "object"
  }
}
```

#### /sequence/progress WebSocket events (updated)

```json
{ "event": "frame_start",    "frame": 1, "total": 10 }
{ "event": "frame_complete", "frame": 1, "file": "light_2026-03-22_0001.cr2" }
{ "event": "bulb_progress",  "elapsed_s": 45.2, "total_s": 120.0 }
{ "event": "fits_ready",     "frame": 1, "paths": {"R": "...", "G": "...", "B": "..."} }
{ "event": "sequence_complete", "frames": 10 }
```

### Non-trivial parts

- **Single-session lock**: only one client connected at a time; idle sessions expire after **30 min** (timer paused while a sequence is running)
- JPEG rendering from CR2 RAW (`rawpy` — already used in `fits_converter.py`)
- Thread safety: camera is a single resource, all hardware calls serialized behind a lock
- Disk space monitoring in `/status` (`shutil.disk_usage`) with low-space warning flag
- HTTP Basic Auth middleware (LAN deployment)
- HA/Airmass computed server-side using astropy at capture time (already done in `fits_converter.py`)

**Estimate: 4–5 weeks** *(was 3–4; +1 week for objects/* endpoints)*

---

## Phase 2 — Desktop Client Refactor (2 weeks)

GTK4 GUI structure stays intact. Only the data source changes.

### What changes

| File | Change |
|------|--------|
| `core/controller.py` | Replaced by thin `api_client.py` (httpx) |
| `gui/app.py` | Instantiates `APIClient` instead of `CameraController` |
| `gui/main_window.py` | Connect/disconnect → HTTP; sequence → HTTP + WebSocket |
| `gui/panels/gear_panel.py` | Reads from `GET /gear/*` instead of `store.load_gear()` |
| `gui/panels/preview_panel.py` | Downloads image from `GET /captures/{id}/raw`; PSF from `/psf`; listens for `fits_ready` WS event |
| `gui/panels/object_panel.py` | Queries `GET /objects/search`, `GET/PUT /objects/selection`, `GET/PUT /objects/location`, favorites API |

### What stays the same

- All `gui/panels/*.py` widget logic — no changes
- `GLib.idle_add()` pattern — works identically with WebSocket callbacks

**Estimate: 2 weeks**

---

## Phase 3 — Rails 8.1.2 Web Client (4–5 weeks)

New application on a separate machine. Communicates with the Python API server.

**Stack:** Rails 8.1.2 · Turbo + Stimulus · ActionCable · Tailwind CSS

| Area | Effort |
|------|--------|
| Project setup, API client service, Basic Auth | 3 days |
| Camera connect/status page + low-storage alert | 2 days |
| Single capture + JPEG preview display | 3 days |
| Sequence configuration form + start/stop | 3 days |
| Live progress (ActionCable → Python WS → Turbo Streams) | 4 days |
| PSF result display (FWHM + radial profile) | 2 days |
| Gear CRUD (camera + optic, catalog browser) | 4 days |
| Object selector (catalog search, HA/Alt/Airmass display) | 3 days *(new)* |
| Observer location (search, favorites) | 2 days *(new)* |
| Capture history/gallery + per-file delete | 3 days |
| RAW file download button | 1 day |
| Polish, error handling, loading states | 3 days |

**Estimate: 5–6 weeks** *(was 4–5; +1 week for object/location pages)*

---

## Total

| Phase | Effort |
|-------|--------|
| Phase 1 — API Server | 4–5 weeks |
| Phase 2 — Desktop refactor | 2 weeks |
| Phase 3 — Rails web client | 5–6 weeks |
| Integration + testing | 1–2 weeks |
| **Total** | **12–15 weeks** |

Phases 2 and 3 can run in parallel once Phase 1 has stable endpoints (~2 weeks in).

---

## Resolved decisions

| Topic | Decision |
|-------|----------|
| Concurrent sessions | One at a time; HTTP 409 for subsequent attempts |
| Session timeout | 30 min idle; paused while sequence is running |
| Auth | HTTP Basic Auth (LAN) |
| Rails version | 8.1.2 |
| Rails machine | Separate from camera server |
| File storage | Server machine; manual delete only |
| File retention | Never auto-deleted; alert shown when disk space is low |
| Low-storage signal | `/status` includes `low_disk: true`; clients display alert |
| PSF analysis | Server-side only |

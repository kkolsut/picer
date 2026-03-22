# Effort Estimate: Picer → Server-Client Architecture

> **Status:** Reference document — no implementation yet. Standalone app continues as-is.

---

## What exists today

**~3,800 LOC across 3 layers:**

| Module | LOC | Notes |
|--------|-----|-------|
| `camera/` + `core/` | 924 | Hardware abstraction + orchestration |
| `gui/` | 1,596 | GTK4 desktop app |
| `gear/` + `utils/` + `cli/` | 1,057 | Catalog, FITS/PSF, CLI |

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
- `utils/fits_converter.py`, `utils/psf.py`, `utils/file_naming.py`
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
| POST | `/sequence` | Start sequence → session ID |
| DELETE | `/sequence` | Stop sequence |
| WS | `/sequence/progress` | Frame progress + bulb progress events |
| GET/POST/PATCH/DELETE | `/gear/cameras` | Camera catalog CRUD |
| GET/POST/PATCH/DELETE | `/gear/optics` | Optic catalog CRUD |
| GET/PUT | `/gear/selection` | Active camera + optic |

### Non-trivial parts

- **Single-session lock**: only one client connected at a time; idle sessions expire after **30 min** (timer paused while a sequence is running)
- JPEG rendering from CR2 RAW (`rawpy` — already used in `fits_converter.py`)
- Thread safety: camera is a single resource, all hardware calls serialized behind a lock
- Disk space monitoring in `/status` (`shutil.disk_usage`) with low-space warning flag
- HTTP Basic Auth middleware (LAN deployment)

**Estimate: 3–4 weeks**

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
| `gui/panels/preview_panel.py` | Downloads image from `GET /captures/{id}/raw`; PSF from `/psf` |

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
| Capture history/gallery + per-file delete | 3 days |
| RAW file download button | 1 day |
| Polish, error handling, loading states | 3 days |

**Estimate: 4–5 weeks**

---

## Total

| Phase | Effort |
|-------|--------|
| Phase 1 — API Server | 3–4 weeks |
| Phase 2 — Desktop refactor | 2 weeks |
| Phase 3 — Rails web client | 4–5 weeks |
| Integration + testing | 1 week |
| **Total** | **10–12 weeks** |

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

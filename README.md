# Picer

Astronomy DSLR capture application for Canon EOS cameras. Controls the camera via USB, captures single frames or multi-frame sequences, converts RAW files to FITS with a full set of astronomical headers, and displays a live preview with PSF analysis.

---

## Features

- **Camera control** — shutter speeds 1/4000 s to 30 s, bulb mode, ISO 100–1600, RAW / JPEG / RAW+JPEG formats
- **Sequences** — light, dark, flat and bias frames; configurable frame count and start-to-start interval
- **Deep Sky Object selector** — search across Messier, Caldwell, NGC, IC, Barnard, LDN, LBN, Abell, UGC and PGC catalogs; displays RA, DEC, live Hour Angle, Altitude and Airmass
- **Observer location** — city/country search (Nominatim/OpenStreetMap, no API key needed), manual lat/lon entry, named favorites
- **Gear management** — built-in catalog of Canon/Nikon/Sony cameras and telescopes/lenses; add and edit custom entries; FOV and plate scale computed automatically
- **Rich FITS headers** — EXPTIME, ISOSPEED, UT-DATE, UT-START, JULDAT, HELJD, OBJECT, IMAGETYP, TELESCOP, DETECTOR, RA, DEC, HA, AIRMASS, SITELAT, SITELONG, FOCALLEN, APTDIA, XPIXSZ/YPIXSZ and more
- **FITS preview** — live stretch, click-to-analyse PSF (FWHM), real-time zoom box
- **FITS header viewer** — inspect the full header of the last captured frame without leaving the app
- **File browser** — browse all captures on the server, select and download RAW (CR2) and/or FITS files to any local directory; optional server-side delete after download
- **REST API** — built-in FastAPI server; web UI (`/docs`) and JSON API available whenever the GUI is running

---

## Architecture

Picer uses a client-server architecture. The **API server** (`picer-api`) controls the camera via libgphoto2 and exposes a REST + WebSocket API. The **GTK GUI** (`picer-gui`) connects to it over HTTP.

```
picer-gui  ──HTTP/WS──►  picer-api  ──USB──►  Canon EOS
```

When running on a **single machine**, `picer-gui` starts the API server automatically in the background — no manual server management needed. For a **headless camera machine** (e.g. Raspberry Pi), run `picer-api` on the Pi and point the GUI on your laptop at it with `--server`.

---

## Requirements

- Linux (tested on Fedora)
- Python 3.11+
- Canon EOS camera connected via USB
- `libgphoto2` installed (`dnf install libgphoto2` / `apt install libgphoto2-dev`)

---

## Installation

```bash
git clone https://github.com/kkolsut/picer.git
cd picer

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Prevent GVFS from grabbing the camera

GVFS auto-mounts cameras as a storage device, which blocks libgphoto2. Install the provided udev rule once:

```bash
sudo cp udev/99-picer-camera.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

If using a camera other than Canon EOS 450D, find your camera's USB vendor/product IDs with `lsusb` and edit the rule accordingly.

---

## Running

### Single machine (most common)

```bash
picer-gui
```

The GUI automatically starts the API server in the background on `127.0.0.1:8765`. Nothing else is needed.

### Headless camera machine (Raspberry Pi, etc.)

On the machine connected to the camera:

```bash
picer-api                        # binds to 0.0.0.0:8765 by default
picer-api --host 0.0.0.0 --port 8765
```

On your laptop / desktop:

```bash
picer-gui --server http://raspberry-pi.local:8765
```

Or set the environment variable instead of the flag:

```bash
export PICER_SERVER_URL=http://raspberry-pi.local:8765
picer-gui
```

### API server options

```
picer-api [--host HOST] [--port PORT] [--log-level LEVEL]

  --host        Bind address (default: 0.0.0.0)
  --port        Port (default: 8765)
  --log-level   debug | info | warning | error (default: info)
```

### Web interface

Whenever the API server is running (including in embedded mode), the auto-generated API docs are available at:

```
http://localhost:8765/docs
```

### CLI — single capture (no GUI)

```bash
picer capture --output ~/captures
picer --help
```

---

## User Guide

### Capture tab

Controls for taking pictures.

| Section | What it does |
|---------|-------------|
| **Exposure** | Select shutter speed or enable Bulb mode and set duration in seconds |
| **ISO** | ISO 100 / 200 / 400 / 800 / 1600 |
| **Format** | RAW (.cr2), JPEG, or RAW + JPEG |
| **Sequence** | Frame type, frame count, start-to-start interval |
| **Output** | Output directory and filename template (see tokens below) |
| **Download** | Download RAW/FITS files from the server after a sequence |
| **FITS Header** | Opens a scrollable view of the last captured frame's FITS header |

**Filename template tokens**

| Token | Example output |
|-------|----------------|
| `{date}` | `2026-03-22` |
| `{time}` | `133000` |
| `{datetime}` | `2026-03-22T133000` |
| `{type}` | `light` / `dark` / `flat` / `bias` |
| `{seq}` | `1` (supports format spec: `{seq:04d}` → `0001`) |
| `{iso}` | `800` |
| `{exp}` | `120s` |
| `{camera}` | `450D` |

Default template: `{type}_{date}_{seq:04d}`

**Frame types**

| Type | Use for |
|------|---------|
| Light | Science frames of your target |
| Dark | Same exposure/ISO as lights, lens cap on |
| Flat | Illuminated flat field for vignetting correction |
| Bias | Shortest exposure, lens cap on |

---

### Download panel

Located at the bottom of the Capture tab.

After a sequence completes, **Download RAW files (N)** is enabled and downloads the just-captured files. Tick **Delete from server after download** to free space on the camera machine automatically.

**Browse…** opens the file browser dialog, which lets you:

- Scan any directory on the server for CR2 captures and their FITS files
- Select individual captures with checkboxes (Select All / Deselect All)
- Choose what to download: **RAW (CR2)**, **FITS (R, G, B channels)**, or both
- Set the local destination directory
- Optionally delete the server copies after downloading

---

### Object tab

Select the target you are imaging. The panel calculates pointing metrics that are written into every FITS header.

1. **Catalog** — choose from M (Messier), C (Caldwell), NGC, IC, Barnard (B), LDN, LBN, Abell, UGC or PGC
2. **Object** — type a number (`42`), full designation (`M 42`, `NGC 1952`) or name substring (`Orion`) and press **Find** or Enter
3. The panel shows designation, type, constellation, RA and DEC (J2000), and updates live:
   - **HA** — Hour Angle (updates every second; `00h 00m 00s` when no location is set)
   - **Alt** — Altitude above horizon
   - **Airmass** — Kasten & Young (1989) formula; shows *below horizon* when Alt ≤ 0°

**Observer location**

| Control | Purpose |
|---------|---------|
| City search + **Search** | Queries Nominatim (OSM); requires internet |
| Result combo + **Use** | Applies selected search result to lat/lon fields |
| **Lat / Lon** | Manual entry in decimal degrees |
| **★ Save location…** | Names and saves the current lat/lon as a favorite |
| Favorites combo + **Use** | Applies a saved favorite |

Location and selected object are saved automatically and restored on next launch.

> **NGC/IC data** — requires downloading the OpenNGC dataset once:
> ```bash
> curl -sL "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv" \
>   -o src/picer/objects/data/NGC.csv
> ```

---

### Gear tab

Describes your optical setup. These values appear in every FITS header and are used to compute FOV and plate scale.

**Camera** — select from the built-in catalog (Canon EOS 350D–90D, Nikon D5300/D7200, Sony α6000/α7III) or add a custom body with **+**. Custom entries can be edited with **✎**.

**Optic** — select a telescope or lens (Sky-Watcher, William Optics, Celestron and Canon/Sigma lens entries included) or add a custom one.

The computed **FOV** and **plate scale** are shown below the selections.

**Custom camera fields**

| Field | Unit |
|-------|------|
| Sensor width / height | mm |
| Resolution (pixels) | px |
| Pixel size | µm |

**Custom optic fields**

| Field | Unit |
|-------|------|
| Focal length | mm |
| Aperture | mm |

---

### Preview panel

After each capture the right-hand panel shows the green-channel FITS image (auto-stretched between the 0.5th and 99.5th percentiles).

- **Click** anywhere on the image → runs a Gaussian PSF fit at that position and shows FWHM in arcseconds (requires gear to be set for the arcsec conversion)
- **Hover** → a real-time zoom box follows the cursor

---

## FITS Headers Written

Every FITS file produced from a RAW capture contains the following headers (where data is available):

```
DATATYP   SHORT                  FITS data pixel type
EXPTIME   120.0                  Exposure time (seconds)
ISOSPEED  800                    ISO speed
UT-DATE   22-03-2026             UT date of start
UT-START  13:30:00               UT time of start
UT-TIME   1774182600             UT time (Unix seconds)
JULDAT    2461122.02             Julian Date
HELJD     2461122.02             Heliocentric Julian Date
OBJECT    M 31                   Object designation
IMAGETYP  object                 Image type (object/dark/flat/bias)
FIELDTYP  unknown                Field type
TELESCOP  Sky-Watcher 80ED       Telescope/optic name
DETECTOR  Canon EOS 450D         Camera/detector name
RA        00:42:44.40            Right ascension J2000
DEC       +41:16:08              Declination J2000
EPOCH     2000.0                 Epoch of RA & DEC
HA        1:17:04.3 W            Hour Angle at capture time
AIRMASS   1.045                  Airmass (Kasten & Young 1989)
SITELAT   52.11                  Observer latitude (deg N)
SITELONG  21.44                  Observer longitude (deg E)
FOCALLEN  600.0                  Focal length (mm)
APTDIA    80.0                   Aperture diameter (mm)
XPIXSZ    5.19                   Pixel size X (µm)
YPIXSZ    5.19                   Pixel size Y (µm)
CCDSEC    [1:2385,1:1589]        Chip image section
DATASEC   [1:2385,1:1589]        Frame image section
CHANNEL   G                      Bayer channel (R / G / B)
BAYER     RGGB                   Bayer pattern
ORIGIN    picer                  Software
```

Each RAW capture produces three FITS files (R, G, B channels). The G channel is used for preview and PSF analysis.

---

## Connecting the Camera

1. Plug the camera in via USB and switch it to **Manual** or **Bulb** mode.
2. Click **Connect** in the top-left of the window. The status dot turns green when connected.
3. Click **Disconnect** before unplugging.

If connection fails, check:
- The udev rule is installed (see Installation)
- No other application (e.g. Darktable, gvfs) is holding the USB device
- The camera is not in PTP/MTP storage mode (switch to remote shooting mode if available)

---

## Persistent Storage

Settings are saved to `~/.config/picer/`:

| File | Contents |
|------|----------|
| `observer.json` | Selected object, observer lat/lon, location favorites |
| `gear.json` | Selected camera/optic, custom camera and optic definitions |

---

## License

MIT

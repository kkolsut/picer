"""CR2 → FITS conversion: extract R, G, B Bayer channels with full FITS headers."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from picer.camera.models import ObservationMetadata


def _ascii(s: str) -> str:
    """Replace non-ASCII characters with '?' so FITS headers never raise."""
    return s.encode("ascii", errors="replace").decode("ascii")

logger = logging.getLogger(__name__)


# ── Coordinate / astronomy helpers ────────────────────────────────────────────

def _fmt_ra_hms(ra_deg: float) -> str:
    total_s = ra_deg * 3600.0 / 15.0
    h = int(total_s // 3600)
    m = int((total_s % 3600) // 60)
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def _fmt_dec_dms(dec_deg: float) -> str:
    sign = "+" if dec_deg >= 0 else "-"
    a = abs(dec_deg)
    d = int(a)
    m = int((a - d) * 60)
    s = int(((a - d) * 60 - m) * 60)
    return f"{sign}{d:02d}:{m:02d}:{s:02d}"


def _fmt_ha_hdr(ha_h: float) -> str:
    """Format HA as 'H:MM:SS.s E/W'."""
    side = "E" if ha_h < 0 else "W"
    a = abs(ha_h)
    h = int(a)
    m = int((a - h) * 60)
    s = (a - h) * 3600 - m * 60
    return f"{h}:{m:02d}:{s:04.1f} {side}"


def _alt_from_ha(ha_h: float, dec_deg: float, lat_deg: float) -> float:
    ha_r = math.radians(ha_h * 15.0)
    d = math.radians(dec_deg)
    l = math.radians(lat_deg)
    return math.degrees(math.asin(
        math.sin(d) * math.sin(l) + math.cos(d) * math.cos(l) * math.cos(ha_r)
    ))


def _airmass(alt_deg: float) -> Optional[float]:
    if alt_deg <= 0:
        return None
    return 1.0 / (math.sin(math.radians(alt_deg))
                  + 0.50572 * (alt_deg + 6.07995) ** -1.6364)


# ── Main converter ─────────────────────────────────────────────────────────────

def cr2_to_fits(
    cr2_path: Path,
    output_dir: Path | None = None,
    metadata: "ObservationMetadata | None" = None,
    capture_time: float | None = None,
    exposure_s: float | None = None,
    iso: int | None = None,
) -> dict[str, Path]:
    """
    Decode CR2 Bayer data and write R.fits, G.fits, B.fits alongside the CR2.
    Returns {"R": path, "G": path, "B": path}.
    G channel = mean of G1 and G2 Bayer planes (half-resolution).
    """
    import rawpy
    import numpy as np
    from astropy.io import fits

    dest = output_dir or cr2_path.parent
    dest.mkdir(parents=True, exist_ok=True)

    with rawpy.imread(str(cr2_path)) as raw:
        bayer = raw.raw_image_visible.copy()
        colors = raw.raw_colors_visible

        # Prefer values passed in from CaptureResult; fall back to rawpy metadata
        if exposure_s is None or exposure_s == 0.0:
            try:
                exposure_s = float(raw.camera_params.exp_time or 0)
            except Exception:
                exposure_s = 0.0
        if iso is None or iso == 0:
            try:
                iso = int(raw.camera_params.iso_speed or 0)
            except Exception:
                iso = 0

        h, w = bayer.shape
        half_h, half_w = h // 2, w // 2

        # Extract channel planes as uint16 (Canon 14-bit values fit in 0-16383)
        r_plane  = bayer[colors == 0].reshape(half_h, half_w)
        g1_plane = bayer[colors == 1].reshape(half_h, half_w).astype(np.int32)
        g2_plane = bayer[colors == 3].reshape(half_h, half_w).astype(np.int32)
        b_plane  = bayer[colors == 2].reshape(half_h, half_w)

    # Average G1+G2, keep as int16 (14-bit values 0-16383 all fit in signed int16)
    g_plane = ((g1_plane + g2_plane) // 2).astype(np.int16)
    r_plane = r_plane.astype(np.int16)
    b_plane = b_plane.astype(np.int16)
    exptime = exposure_s

    stem = cr2_path.stem
    channels = {"R": r_plane, "G": g_plane, "B": b_plane}
    paths: dict[str, Path] = {}

    for ch, data in channels.items():
        hdr = _build_header(ch, exptime, iso or 0, data.shape, metadata, capture_time)
        out_path = dest / f"{stem}_{ch}.fits"
        fits.writeto(str(out_path), data, hdr, overwrite=True)
        paths[ch] = out_path
        logger.debug("Wrote %s", out_path)

    return paths


def _build_header(
    ch: str,
    exptime: float,
    iso: int,
    data_shape: tuple[int, int],
    metadata: "ObservationMetadata | None",
    capture_time: float | None,
):
    from astropy.io import fits

    hdr = fits.Header()

    # ── Pixel / exposure ──────────────────────────────────────────────────
    hdr["DATATYP"]  = ("SHORT",   "FITS data pixel type")
    hdr["EXPTIME"]  = (exptime,   "Exposure Time (seconds)")
    hdr["ISOSPEED"] = (iso,       "ISO speed")

    # ── Date / time ───────────────────────────────────────────────────────
    if capture_time is not None:
        dt = datetime.fromtimestamp(capture_time, tz=timezone.utc)
        hdr["UT-DATE"]  = (dt.strftime("%d-%m-%Y"), "UT date of start")
        hdr["UT-START"] = (dt.strftime("%H:%M:%S"), "UT time of start")
        hdr["UT-TIME"]  = (int(capture_time),        "UT time of start (Unix seconds)")
        try:
            from astropy.time import Time
            t = Time(capture_time, format="unix")
            hdr["JULDAT"] = (round(t.jd, 5), "Julian Date")
        except Exception:
            pass

    # ── Heliocentric JD (needs RA+Dec+time) ───────────────────────────────
    if (capture_time is not None
            and metadata is not None
            and metadata.ra_deg is not None
            and metadata.dec_deg is not None):
        try:
            from astropy.time import Time
            from astropy.coordinates import SkyCoord
            import astropy.units as u
            t = Time(capture_time, format="unix")
            coord = SkyCoord(ra=metadata.ra_deg * u.deg,
                             dec=metadata.dec_deg * u.deg, frame="icrs")
            ltt = t.light_travel_time(coord, "heliocentric")
            hdr["HELJD"] = (round((t + ltt).jd, 5), "Heliocentric Julian Date")
        except Exception:
            pass

    # ── Observation context ───────────────────────────────────────────────
    if metadata is not None:
        if metadata.object_name:
            hdr["OBJECT"]   = (_ascii(metadata.object_name), "Object name")
        if metadata.frame_type:
            hdr["IMAGETYP"] = (_ascii(metadata.frame_type),  "Image type")
        hdr["FIELDTYP"] = ("unknown", "Field type")
        if metadata.telescope:
            hdr["TELESCOP"] = (_ascii(metadata.telescope),   "Telescope / optic")
        if metadata.detector:
            hdr["DETECTOR"] = (_ascii(metadata.detector),    "Camera / detector")

        # ── Coordinates ───────────────────────────────────────────────────
        if metadata.ra_deg is not None and metadata.dec_deg is not None:
            hdr["RA"]    = (_fmt_ra_hms(metadata.ra_deg),   "Right ascension J2000")
            hdr["DEC"]   = (_fmt_dec_dms(metadata.dec_deg), "Declination J2000")
            hdr["EPOCH"] = (2000.0,                          "Epoch of RA & DEC")

        # ── HA and Airmass (computed at capture time) ──────────────────────
        if (capture_time is not None
                and metadata.ra_deg is not None
                and metadata.observer_lon is not None):
            try:
                from astropy.time import Time
                import astropy.units as u
                t = Time(capture_time, format="unix")
                lst = t.sidereal_time("apparent", longitude=metadata.observer_lon * u.deg)
                ha_h = lst.hour - metadata.ra_deg / 15.0
                while ha_h > 12:
                    ha_h -= 24
                while ha_h <= -12:
                    ha_h += 24
                hdr["HA"] = (_fmt_ha_hdr(ha_h), "Hour Angle")

                if metadata.observer_lat is not None and metadata.dec_deg is not None:
                    alt = _alt_from_ha(ha_h, metadata.dec_deg, metadata.observer_lat)
                    am = _airmass(alt)
                    if am is not None:
                        hdr["AIRMASS"] = (round(am, 4), "Airmass (Kasten & Young 1989)")
            except Exception:
                pass

        # ── Observer location ─────────────────────────────────────────────
        if metadata.observer_lat is not None:
            hdr["SITELAT"]  = (metadata.observer_lat, "Observer latitude (deg N)")
        if metadata.observer_lon is not None:
            hdr["SITELONG"] = (metadata.observer_lon, "Observer longitude (deg E)")

        # ── Optics ────────────────────────────────────────────────────────
        if metadata.focal_mm is not None:
            hdr["FOCALLEN"] = (metadata.focal_mm,    "Focal length (mm)")
        if metadata.aperture_mm is not None:
            hdr["APTDIA"]   = (metadata.aperture_mm, "Aperture diameter (mm)")
        if metadata.pixel_um is not None:
            hdr["XPIXSZ"]   = (metadata.pixel_um,   "Pixel size X (um)")
            hdr["YPIXSZ"]   = (metadata.pixel_um,   "Pixel size Y (um)")

    # ── Image section ─────────────────────────────────────────────────────
    ny, nx = data_shape
    sec = f"[1:{nx},1:{ny}]"
    hdr["CCDSEC"]  = (sec, "Chip image section")
    hdr["DATASEC"] = (sec, "Frame image section")

    # ── Instrument / provenance ───────────────────────────────────────────
    hdr["CHANNEL"] = (ch,       "Bayer channel (R / G / B)")
    hdr["BAYER"]   = ("RGGB",   "Bayer pattern")
    hdr["ORIGIN"]  = ("picer",  "Software")

    return hdr

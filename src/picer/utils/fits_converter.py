"""CR2 → FITS conversion: extract R, G, B Bayer channels."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def cr2_to_fits(cr2_path: Path, output_dir: Path | None = None) -> dict[str, Path]:
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
        bayer = raw.raw_image_visible.copy()          # uint16, full Bayer grid
        colors = raw.raw_colors_visible               # 0=R, 1=G1, 2=G2, 3=B

        # Extract metadata for FITS header
        try:
            exptime = float(raw.camera_params.exp_time or 0)
        except Exception:
            exptime = 0.0
        try:
            iso = int(raw.camera_params.iso_speed or 0)
        except Exception:
            iso = 0

        h, w = bayer.shape
        half_h, half_w = h // 2, w // 2

        # Each color occupies one quadrant of a 2×2 Bayer tile.
        # Slice each channel plane from the full grid.
        r_plane  = bayer[colors == 0].reshape(half_h, half_w).astype(np.float32)
        g1_plane = bayer[colors == 1].reshape(half_h, half_w).astype(np.float32)
        g2_plane = bayer[colors == 3].reshape(half_h, half_w).astype(np.float32)
        b_plane  = bayer[colors == 2].reshape(half_h, half_w).astype(np.float32)

    g_plane = ((g1_plane + g2_plane) / 2).astype(np.float32)

    stem = cr2_path.stem
    channels = {"R": r_plane, "G": g_plane, "B": b_plane}
    paths: dict[str, Path] = {}

    for ch, data in channels.items():
        hdr = fits.Header()
        hdr["INSTRUME"] = "Canon EOS CR2"
        hdr["EXPTIME"]  = exptime
        hdr["ISOSPEED"] = iso
        hdr["CHANNEL"]  = ch
        hdr["BAYER"]    = "RGGB"
        hdr["ORIGIN"]   = "picer"
        out_path = dest / f"{stem}_{ch}.fits"
        fits.writeto(str(out_path), data, hdr, overwrite=True)
        paths[ch] = out_path
        logger.debug("Wrote %s", out_path)

    return paths

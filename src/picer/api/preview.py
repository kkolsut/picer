"""Image rendering: CR2 → JPEG and FITS → JPEG."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np


def cr2_to_jpeg(cr2_path: Path, max_size: int = 1920) -> bytes:
    """Decode a CR2 RAW file and return JPEG bytes."""
    import rawpy
    from PIL import Image

    with rawpy.imread(str(cr2_path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=False)

    img = Image.fromarray(rgb)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def fits_to_jpeg(fits_path: Path, max_size: int = 1920) -> bytes:
    """Load a FITS image, apply percentile stretch, and return JPEG bytes."""
    from astropy.io import fits as astrofits
    from PIL import Image

    data = astrofits.getdata(str(fits_path)).astype(np.float64)
    p_lo, p_hi = np.percentile(data, [0.5, 99.5])
    if p_hi <= p_lo:
        p_hi = p_lo + 1.0

    stretched = np.clip((data - p_lo) / (p_hi - p_lo), 0.0, 1.0)
    img_data = (stretched * 255).astype(np.uint8)

    img = Image.fromarray(img_data, mode="L").convert("RGB")
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

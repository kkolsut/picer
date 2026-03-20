"""PSF (Point Spread Function) analysis — Gaussian fit and FWHM computation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PSFResult:
    fit_ok: bool = False
    fit_error: str = ""
    fwhm_px: float = 0.0
    sigma_px: float = 0.0
    amplitude: float = 0.0
    background: float = 0.0
    # Radial profile arrays (for plotting)
    r_values: list[float] = field(default_factory=list)
    i_values: list[float] = field(default_factory=list)
    # Gaussian fit curve (for plotting)
    fit_r: list[float] = field(default_factory=list)
    fit_i: list[float] = field(default_factory=list)
    # Click location (informational)
    fits_x: int = 0
    fits_y: int = 0


def compute_psf(
    fits_path: Path,
    fits_x: int,
    fits_y: int,
    cutout_size: int = 64,
) -> PSFResult:
    """
    Compute PSF FWHM for a star at (fits_x, fits_y) in fits_path.
    Returns a PSFResult; fit_ok=False on failure.
    """
    try:
        from astropy.io import fits as astrofits
        from scipy.optimize import curve_fit
    except ImportError as exc:
        return PSFResult(fit_ok=False, fit_error=f"Missing dependency: {exc}")

    # ── Load data ─────────────────────────────────────────────────────
    try:
        data = astrofits.getdata(str(fits_path)).astype(np.float64)
    except Exception as exc:
        return PSFResult(fit_ok=False, fit_error=f"Cannot read FITS: {exc}")

    img_h, img_w = data.shape

    # ── Extract cutout ────────────────────────────────────────────────
    half = cutout_size // 2
    x0 = max(0, fits_x - half)
    x1 = min(img_w, fits_x + half)
    y0 = max(0, fits_y - half)
    y1 = min(img_h, fits_y + half)

    if (x1 - x0) < 8 or (y1 - y0) < 8:
        return PSFResult(
            fit_ok=False, fit_error="Cutout too small (near image edge)",
            fits_x=fits_x, fits_y=fits_y,
        )

    cutout = data[y0:y1, x0:x1].copy()

    # ── Background: median of 4-pixel border ring ─────────────────────
    border_mask = np.zeros(cutout.shape, dtype=bool)
    ring = 4
    border_mask[:ring, :]  = True
    border_mask[-ring:, :] = True
    border_mask[:, :ring]  = True
    border_mask[:, -ring:] = True
    background = float(np.median(cutout[border_mask]))
    cutout -= background
    np.clip(cutout, 0, None, out=cutout)

    # ── Intensity-weighted centroid ────────────────────────────────────
    total = cutout.sum()
    if total <= 0:
        return PSFResult(
            fit_ok=False, fit_error="No signal above background",
            fits_x=fits_x, fits_y=fits_y,
        )
    cy_h, cy_w = cutout.shape
    yy, xx = np.mgrid[0:cy_h, 0:cy_w]
    cx = float((xx * cutout).sum() / total)
    cy = float((yy * cutout).sum() / total)

    # ── Radial profile ─────────────────────────────────────────────────
    r_map = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_int = r_map.astype(int)
    max_r = int(r_int.max())

    r_values: list[float] = []
    i_values: list[float] = []
    for r in range(max_r + 1):
        mask = r_int == r
        if mask.sum() == 0:
            continue
        r_values.append(float(r))
        i_values.append(float(np.median(cutout[mask])))

    if len(r_values) < 4:
        return PSFResult(
            fit_ok=False, fit_error="Too few radial bins",
            r_values=r_values, i_values=i_values,
            fits_x=fits_x, fits_y=fits_y,
        )

    r_arr = np.array(r_values)
    i_arr = np.array(i_values)

    # ── Gaussian fit: A·exp(-r²/2σ²) ──────────────────────────────────
    A0 = float(i_arr[0]) if i_arr[0] > 0 else float(i_arr.max())
    sigma0 = float(r_arr[len(r_arr) // 4]) if len(r_arr) >= 4 else 2.0

    def gaussian(r: np.ndarray, A: float, sigma: float) -> np.ndarray:
        return A * np.exp(-(r ** 2) / (2 * sigma ** 2))

    try:
        popt, _ = curve_fit(
            gaussian, r_arr, i_arr,
            p0=[A0, max(sigma0, 0.5)],
            bounds=([0, 0.1], [np.inf, half]),
            maxfev=2000,
        )
    except Exception as exc:
        return PSFResult(
            fit_ok=False, fit_error=f"Fit failed: {exc}",
            r_values=r_values, i_values=i_values,
            fits_x=fits_x, fits_y=fits_y,
        )

    A_fit, sigma_fit = float(popt[0]), float(popt[1])
    fwhm = 2.3548 * sigma_fit

    # Dense fit curve for plotting
    fit_r_arr = np.linspace(0, r_arr[-1], 200)
    fit_i_arr = gaussian(fit_r_arr, A_fit, sigma_fit)

    return PSFResult(
        fit_ok=True,
        fwhm_px=fwhm,
        sigma_px=sigma_fit,
        amplitude=A_fit,
        background=background,
        r_values=r_values,
        i_values=i_values,
        fit_r=fit_r_arr.tolist(),
        fit_i=fit_i_arr.tolist(),
        fits_x=fits_x,
        fits_y=fits_y,
    )

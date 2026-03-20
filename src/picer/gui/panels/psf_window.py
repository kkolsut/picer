"""Floating PSF result window with Cairo-drawn radial profile."""
from __future__ import annotations

import math
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

try:
    gi.require_version("cairo", "1.0")
    import cairo  # noqa: E402 (pycairo)
    _HAS_CAIRO = True
except Exception:
    _HAS_CAIRO = False

from picer.utils.psf import PSFResult


class PsfWindow(Gtk.Window):
    """Floating window showing a star's radial PSF profile and FWHM."""

    _DRAW_W = 380
    _DRAW_H = 260

    def __init__(self, parent: Gtk.Window) -> None:
        super().__init__()
        self.set_transient_for(parent)
        self.set_default_size(420, 400)
        self.set_title("Star Profile")
        self.set_resizable(False)

        self._result: Optional[PSFResult] = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        self.set_child(outer)

        # Header label
        self._header_label = Gtk.Label(label="Click a star to analyse its PSF")
        self._header_label.add_css_class("dim-label")
        outer.append(self._header_label)

        # Drawing area
        self._area = Gtk.DrawingArea()
        self._area.set_content_width(self._DRAW_W)
        self._area.set_content_height(self._DRAW_H)
        self._area.set_draw_func(self._draw_profile)
        outer.append(self._area)

        # Result label
        self._result_label = Gtk.Label(label="")
        self._result_label.set_xalign(0.5)
        self._result_label.set_wrap(True)
        outer.append(self._result_label)

    # ------------------------------------------------------------------

    def update(self, result: PSFResult, fits_x: int, fits_y: int) -> None:
        self._result = result
        self._header_label.set_text(f"Star PSF  —  pixel ({fits_x}, {fits_y})")
        if result.fit_ok:
            self._result_label.set_markup(
                f"<b>FWHM = {result.fwhm_px:.2f} px</b>   "
                f"σ = {result.sigma_px:.2f} px   "
                f"A = {result.amplitude:.0f}   "
                f"bg = {result.background:.0f}"
            )
        elif result.r_values:
            self._result_label.set_text(f"Fit failed: {result.fit_error}")
        else:
            self._result_label.set_text(result.fit_error or "No data")
        self._area.queue_draw()

    # ------------------------------------------------------------------
    # Cairo drawing
    # ------------------------------------------------------------------

    def _draw_profile(
        self,
        area: Gtk.DrawingArea,
        cr: "cairo.Context",
        width: int,
        height: int,
    ) -> None:
        if not _HAS_CAIRO:
            return

        result = self._result

        # ── Background ────────────────────────────────────────────────
        cr.set_source_rgb(0.10, 0.10, 0.12)
        cr.paint()

        if result is None or (not result.r_values and not result.fit_ok):
            self._draw_message(cr, width, height, "No data")
            return

        # ── Layout ────────────────────────────────────────────────────
        pad_l, pad_r, pad_t, pad_b = 52, 20, 20, 40
        plot_w = width  - pad_l - pad_r
        plot_h = height - pad_t - pad_b

        r_vals = result.r_values
        i_vals = result.i_values
        r_max  = max(r_vals) if r_vals else 1.0
        i_max  = max(i_vals) if i_vals else 1.0
        if result.fit_ok:
            i_max = max(i_max, result.amplitude)

        def px(r: float, i: float) -> tuple[float, float]:
            sx = pad_l + (r / r_max) * plot_w
            sy = pad_t + plot_h - (i / i_max) * plot_h
            return sx, sy

        # ── Axes ──────────────────────────────────────────────────────
        cr.set_source_rgb(0.4, 0.4, 0.4)
        cr.set_line_width(1)
        # x-axis
        cr.move_to(pad_l, pad_t + plot_h)
        cr.line_to(pad_l + plot_w, pad_t + plot_h)
        cr.stroke()
        # y-axis
        cr.move_to(pad_l, pad_t)
        cr.line_to(pad_l, pad_t + plot_h)
        cr.stroke()

        # ── Tick marks & labels ───────────────────────────────────────
        cr.set_source_rgb(0.55, 0.55, 0.55)
        cr.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)

        # x ticks: 0, r_max/2, r_max
        for frac, label in [(0.0, "0"), (0.5, f"{r_max/2:.1f}"), (1.0, f"{r_max:.0f}")]:
            tx = pad_l + frac * plot_w
            ty = pad_t + plot_h
            cr.move_to(tx, ty)
            cr.line_to(tx, ty + 4)
            cr.stroke()
            cr.move_to(tx - 10, ty + 14)
            cr.show_text(label)

        # x-axis label
        cr.move_to(pad_l + plot_w / 2 - 20, height - 4)
        cr.show_text("radius (px)")

        # y ticks: 0, i_max/2, i_max
        for frac, label in [(0.0, f"{i_max:.0f}"), (0.5, f"{i_max/2:.0f}"), (1.0, "0")]:
            ty_t = pad_t + frac * plot_h
            cr.move_to(pad_l - 4, ty_t)
            cr.line_to(pad_l, ty_t)
            cr.stroke()
            cr.move_to(2, ty_t + 4)
            cr.show_text(label)

        # ── Half-max dotted line ───────────────────────────────────────
        if result.fit_ok:
            half_max = result.amplitude / 2
            hm_y = pad_t + plot_h - (half_max / i_max) * plot_h
            cr.set_source_rgba(0.7, 0.7, 0.3, 0.6)
            cr.set_line_width(1)
            cr.set_dash([4, 4])
            cr.move_to(pad_l, hm_y)
            cr.line_to(pad_l + plot_w, hm_y)
            cr.stroke()
            cr.set_dash([])

            # FWHM ticks on x-axis
            half_fwhm = result.fwhm_px / 2
            for xf in [-half_fwhm, half_fwhm]:
                tx = pad_l + ((xf + result.sigma_px * 0) / r_max) * plot_w
                # draw at r=half_fwhm from centroid (centroid is at r=0)
                tx = pad_l + (abs(xf) / r_max) * plot_w
                cr.set_source_rgba(0.9, 0.6, 0.1, 0.9)
                cr.move_to(tx, hm_y - 5)
                cr.line_to(tx, hm_y + 5)
                cr.stroke()

            # FWHM annotation
            cr.set_source_rgb(0.95, 0.75, 0.2)
            cr.set_font_size(11)
            fwhm_text = f"FWHM = {result.fwhm_px:.2f} px"
            cr.move_to(pad_l + 6, pad_t + 16)
            cr.show_text(fwhm_text)

        # ── Raw radial profile (blue dots + line) ─────────────────────
        if r_vals:
            cr.set_source_rgb(0.3, 0.55, 0.9)
            cr.set_line_width(1.5)
            first = True
            for r, i in zip(r_vals, i_vals):
                sx, sy = px(r, i)
                if first:
                    cr.move_to(sx, sy)
                    first = False
                else:
                    cr.line_to(sx, sy)
            cr.stroke()

            cr.set_source_rgb(0.3, 0.55, 0.9)
            for r, i in zip(r_vals, i_vals):
                sx, sy = px(r, i)
                cr.arc(sx, sy, 2.5, 0, 2 * math.pi)
                cr.fill()

        # ── Gaussian fit curve (orange) ───────────────────────────────
        if result.fit_ok and result.fit_r:
            cr.set_source_rgb(0.95, 0.5, 0.1)
            cr.set_line_width(2)
            first = True
            for r, i in zip(result.fit_r, result.fit_i):
                sx, sy = px(r, i)
                if first:
                    cr.move_to(sx, sy)
                    first = False
                else:
                    cr.line_to(sx, sy)
            cr.stroke()

        # ── Error message overlay ─────────────────────────────────────
        if not result.fit_ok and result.fit_error:
            cr.set_source_rgba(0.9, 0.3, 0.3, 0.85)
            cr.set_font_size(11)
            cr.move_to(pad_l + 6, pad_t + 18)
            cr.show_text(result.fit_error)

    @staticmethod
    def _draw_message(
        cr: "cairo.Context", width: int, height: int, msg: str
    ) -> None:
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(13)
        cr.move_to(width / 2 - 40, height / 2)
        cr.show_text(msg)

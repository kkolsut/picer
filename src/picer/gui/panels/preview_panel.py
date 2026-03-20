"""Preview panel: display G-channel FITS preview; click → PSF analysis."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

try:
    import cairo
    _HAS_CAIRO = True
except ImportError:
    _HAS_CAIRO = False

from picer.utils.psf import PSFResult


class PreviewPanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="Last Capture")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._stack = Gtk.Stack()

        # Placeholder page
        self._placeholder_label = Gtk.Label(label="No image captured yet")
        self._placeholder_label.add_css_class("dim-label")
        self._stack.add_named(self._placeholder_label, "placeholder")

        # Image page
        self._image = Gtk.Picture()
        self._image.set_can_shrink(True)
        self._image.set_content_fit(Gtk.ContentFit.CONTAIN)
        self._stack.add_named(self._image, "image")

        # Info label
        self._info_label = Gtk.Label()
        self._info_label.set_xalign(0.5)
        self._info_label.add_css_class("dim-label")

        # FWHM label
        self._fwhm_label = Gtk.Label(label="")
        self._fwhm_label.set_xalign(0.5)

        # PSF drawing area (hidden until first click)
        self._psf_area = Gtk.DrawingArea()
        self._psf_area.set_content_width(380)
        self._psf_area.set_content_height(220)
        self._psf_area.set_draw_func(self._draw_psf)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.append(self._stack)
        outer.append(self._info_label)
        outer.append(self._fwhm_label)
        outer.append(self._psf_area)
        self.set_child(outer)

        self._stack.set_visible_child_name("placeholder")

        # State
        self._current_fits_path: Optional[Path] = None
        self._current_img_w: int = 0
        self._current_img_h: int = 0
        self._psf_result: Optional[PSFResult] = None

        # Click gesture on image widget
        gesture = Gtk.GestureClick.new()
        gesture.set_button(1)
        gesture.connect("pressed", self._on_image_clicked)
        self._image.add_controller(gesture)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_file(self, path: Path, exposure_s: float, iso: int) -> None:
        if path.suffix.lower() == ".cr2":
            self._placeholder_label.set_label("Converting to FITS…")
            self._stack.set_visible_child_name("placeholder")
            self._info_label.set_text(
                f"{path.name}  |  {exposure_s:.3g}s  |  ISO {iso}"
            )
        elif path.suffix.lower() in (".fits", ".fit"):
            self.show_fits(path, exposure_s, iso)
        else:
            self._placeholder_label.set_label(f"Captured (no preview for {path.suffix})")
            self._stack.set_visible_child_name("placeholder")
            self._info_label.set_text(
                f"{path.name}  |  {exposure_s:.3g}s  |  ISO {iso}"
            )

    def show_fits(self, fits_path: Path, exposure_s: float, iso: int) -> None:
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        import numpy as np

        try:
            from astropy.io import fits as astrofits
            data = astrofits.getdata(str(fits_path)).astype(np.float64)
        except Exception as exc:
            self._placeholder_label.set_label(f"FITS load error: {exc}")
            self._stack.set_visible_child_name("placeholder")
            return

        lo, hi = np.percentile(data, [0.5, 99.5])
        span = hi - lo if hi != lo else 1.0
        stretched = np.clip((data - lo) / span, 0, 1)
        grey = (stretched * 255).astype(np.uint8)

        h, w = grey.shape
        rgb = np.stack([grey, grey, grey], axis=-1).copy()

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            rgb.tobytes(), GdkPixbuf.Colorspace.RGB, False, 8, w, h, w * 3,
        )
        self._image.set_pixbuf(pixbuf)
        self._stack.set_visible_child_name("image")

        self._current_fits_path = fits_path
        self._current_img_w = w
        self._current_img_h = h

        self._info_label.set_text(
            f"{fits_path.name}  |  {exposure_s:.3g}s  |  ISO {iso}  |  {w}×{h} px"
        )

        # Reset PSF on new image
        self._psf_result = None
        self._fwhm_label.set_text("")
        self._psf_area.queue_draw()

    def clear(self) -> None:
        self._placeholder_label.set_label("No image captured yet")
        self._stack.set_visible_child_name("placeholder")
        self._info_label.set_text("")
        self._fwhm_label.set_text("")
        self._current_fits_path = None
        self._psf_result = None
        self._psf_area.queue_draw()

    # ------------------------------------------------------------------
    # Click → PSF
    # ------------------------------------------------------------------

    def _on_image_clicked(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        if self._current_fits_path is None:
            return

        widget = gesture.get_widget()
        widget_w = widget.get_width()
        widget_h = widget.get_height()
        img_w = self._current_img_w
        img_h = self._current_img_h

        if widget_w <= 0 or widget_h <= 0 or img_w <= 0 or img_h <= 0:
            return

        scale = min(widget_w / img_w, widget_h / img_h)
        ox = (widget_w - img_w * scale) / 2
        oy = (widget_h - img_h * scale) / 2
        px = int((x - ox) / scale)
        py = int((y - oy) / scale)

        if not (0 <= px < img_w and 0 <= py < img_h):
            return

        from picer.utils.psf import compute_psf
        self._psf_result = compute_psf(self._current_fits_path, px, py)

        if self._psf_result.fit_ok:
            self._fwhm_label.set_markup(
                f"<b>FWHM = {self._psf_result.fwhm_px:.2f} px</b>"
            )
        else:
            self._fwhm_label.set_text(
                f"FWHM: {self._psf_result.fit_error or 'fit failed'}"
            )

        self._psf_area.queue_draw()

    # ------------------------------------------------------------------
    # Cairo PSF plot
    # ------------------------------------------------------------------

    def _draw_psf(
        self,
        area: Gtk.DrawingArea,
        cr: "cairo.Context",
        width: int,
        height: int,
    ) -> None:
        if not _HAS_CAIRO:
            return

        result = self._psf_result

        # Background
        cr.set_source_rgb(0.10, 0.10, 0.12)
        cr.paint()

        if result is None:
            cr.set_source_rgb(0.25, 0.25, 0.28)
            cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(12)
            msg = "Click a star to analyse its PSF"
            cr.move_to(width / 2 - 100, height / 2)
            cr.show_text(msg)
            return

        if not result.r_values and not result.fit_ok:
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(13)
            cr.move_to(width / 2 - 30, height / 2)
            cr.show_text("No data")
            return

        pad_l, pad_r, pad_t, pad_b = 52, 20, 20, 40
        plot_w = width  - pad_l - pad_r
        plot_h = height - pad_t - pad_b

        r_vals = result.r_values
        i_vals = result.i_values
        r_max  = max(r_vals) if r_vals else 1.0
        i_max  = max(i_vals) if i_vals else 1.0
        if result.fit_ok:
            i_max = max(i_max, result.amplitude)

        def to_screen(r: float, i: float) -> tuple[float, float]:
            sx = pad_l + (r / r_max) * plot_w
            sy = pad_t + plot_h - (i / i_max) * plot_h
            return sx, sy

        # Axes
        cr.set_source_rgb(0.4, 0.4, 0.4)
        cr.set_line_width(1)
        cr.move_to(pad_l, pad_t + plot_h)
        cr.line_to(pad_l + plot_w, pad_t + plot_h)
        cr.stroke()
        cr.move_to(pad_l, pad_t)
        cr.line_to(pad_l, pad_t + plot_h)
        cr.stroke()

        # Tick marks & labels
        cr.set_source_rgb(0.55, 0.55, 0.55)
        cr.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        for frac, label in [(0.0, "0"), (0.5, f"{r_max/2:.1f}"), (1.0, f"{r_max:.0f}")]:
            tx = pad_l + frac * plot_w
            ty = pad_t + plot_h
            cr.move_to(tx, ty); cr.line_to(tx, ty + 4); cr.stroke()
            cr.move_to(tx - 10, ty + 14); cr.show_text(label)
        cr.move_to(pad_l + plot_w / 2 - 20, height - 4)
        cr.show_text("radius (px)")
        for frac, label in [(0.0, f"{i_max:.0f}"), (0.5, f"{i_max/2:.0f}"), (1.0, "0")]:
            ty_t = pad_t + frac * plot_h
            cr.move_to(pad_l - 4, ty_t); cr.line_to(pad_l, ty_t); cr.stroke()
            cr.move_to(2, ty_t + 4); cr.show_text(label)

        # Half-max dotted line + FWHM ticks
        if result.fit_ok:
            half_max = result.amplitude / 2
            hm_y = pad_t + plot_h - (half_max / i_max) * plot_h
            cr.set_source_rgba(0.7, 0.7, 0.3, 0.6)
            cr.set_line_width(1)
            cr.set_dash([4, 4])
            cr.move_to(pad_l, hm_y); cr.line_to(pad_l + plot_w, hm_y); cr.stroke()
            cr.set_dash([])
            half_fwhm = result.fwhm_px / 2
            for xf in [half_fwhm, result.fwhm_px]:
                tx = pad_l + (xf / r_max) * plot_w if xf <= r_max else pad_l + plot_w
                cr.set_source_rgba(0.9, 0.6, 0.1, 0.9)
                cr.move_to(tx, hm_y - 5); cr.line_to(tx, hm_y + 5); cr.stroke()
            cr.set_source_rgb(0.95, 0.75, 0.2)
            cr.set_font_size(11)
            cr.move_to(pad_l + 6, pad_t + 16)
            cr.show_text(f"FWHM = {result.fwhm_px:.2f} px")

        # Raw radial profile (blue)
        if r_vals:
            cr.set_source_rgb(0.3, 0.55, 0.9)
            cr.set_line_width(1.5)
            first = True
            for r, i in zip(r_vals, i_vals):
                sx, sy = to_screen(r, i)
                if first: cr.move_to(sx, sy); first = False
                else: cr.line_to(sx, sy)
            cr.stroke()
            for r, i in zip(r_vals, i_vals):
                sx, sy = to_screen(r, i)
                cr.arc(sx, sy, 2.5, 0, 2 * math.pi)
                cr.fill()

        # Gaussian fit curve (orange)
        if result.fit_ok and result.fit_r:
            cr.set_source_rgb(0.95, 0.5, 0.1)
            cr.set_line_width(2)
            first = True
            for r, i in zip(result.fit_r, result.fit_i):
                sx, sy = to_screen(r, i)
                if first: cr.move_to(sx, sy); first = False
                else: cr.line_to(sx, sy)
            cr.stroke()

        # Error overlay
        if not result.fit_ok and result.fit_error:
            cr.set_source_rgba(0.9, 0.3, 0.3, 0.85)
            cr.set_font_size(11)
            cr.move_to(pad_l + 6, pad_t + 18)
            cr.show_text(result.fit_error)

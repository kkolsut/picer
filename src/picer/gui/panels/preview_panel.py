"""Preview panel: display G-channel FITS preview; click → PSF analysis."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


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

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(8)
        outer.set_margin_end(8)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.append(self._stack)
        outer.append(self._info_label)
        self.set_child(outer)

        self._stack.set_visible_child_name("placeholder")

        # State for click → PSF
        self._current_fits_path: Optional[Path] = None
        self._current_img_w: int = 0
        self._current_img_h: int = 0
        self._psf_window = None

        # Click gesture on image widget
        gesture = Gtk.GestureClick.new()
        gesture.set_button(1)
        gesture.connect("pressed", self._on_image_clicked)
        self._image.add_controller(gesture)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_file(self, path: Path, exposure_s: float, iso: int) -> None:
        """Called immediately after capture; shows placeholder while FITS is being built."""
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
        """Decode and display a FITS file (G channel preview)."""
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

        # Percentile stretch
        lo, hi = np.percentile(data, [0.5, 99.5])
        span = hi - lo if hi != lo else 1.0
        stretched = np.clip((data - lo) / span, 0, 1)
        grey = (stretched * 255).astype(np.uint8)

        h, w = grey.shape
        rgb = np.stack([grey, grey, grey], axis=-1).copy()

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            rgb.tobytes(),
            GdkPixbuf.Colorspace.RGB,
            False,
            8,
            w,
            h,
            w * 3,
        )
        self._image.set_pixbuf(pixbuf)
        self._stack.set_visible_child_name("image")

        self._current_fits_path = fits_path
        self._current_img_w = w
        self._current_img_h = h

        self._info_label.set_text(
            f"{fits_path.name}  |  {exposure_s:.3g}s  |  ISO {iso}  |  {w}×{h} px"
        )

    def clear(self) -> None:
        self._placeholder_label.set_label("No image captured yet")
        self._stack.set_visible_child_name("placeholder")
        self._info_label.set_text("")
        self._current_fits_path = None

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

        # CONTAIN scaling: map click to FITS pixel
        scale = min(widget_w / img_w, widget_h / img_h)
        ox = (widget_w - img_w * scale) / 2
        oy = (widget_h - img_h * scale) / 2
        px = int((x - ox) / scale)
        py = int((y - oy) / scale)

        if not (0 <= px < img_w and 0 <= py < img_h):
            return  # click in letterbox area

        from picer.utils.psf import compute_psf

        result = compute_psf(self._current_fits_path, px, py)

        # Lazy-init PSF window
        if self._psf_window is None:
            from picer.gui.panels.psf_window import PsfWindow
            root = self.get_root()
            parent_win = root if isinstance(root, Gtk.Window) else None
            self._psf_window = PsfWindow(parent_win)

        self._psf_window.update(result, px, py)
        self._psf_window.present()

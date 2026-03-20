"""Preview panel: thumbnail of last capture."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def _extract_embedded_jpeg(path: Path) -> Optional[bytes]:
    """
    Extract the largest *valid* embedded JPEG from a CR2/RAW file.
    Canon CR2 files contain multiple embedded JPEGs; we try each and return
    the largest one that GdkPixbuf can actually decode.
    """
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf  # local import to avoid circular gi issues

    data = path.read_bytes()
    JPEG_START = b"\xff\xd8\xff"
    JPEG_END = b"\xff\xd9"

    segments: list[bytes] = []
    pos = 0
    while True:
        start = data.find(JPEG_START, pos)
        if start == -1:
            break
        end = data.find(JPEG_END, start)
        if end == -1:
            break
        segments.append(data[start : end + 2])
        pos = end + 2

    # Try each segment; keep the largest that successfully loads
    best: Optional[bytes] = None
    for segment in segments:
        try:
            loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
            loader.write(segment)
            loader.close()
            if loader.get_pixbuf() is not None:
                if best is None or len(segment) > len(best):
                    best = segment
        except Exception:
            pass

    return best


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

    def show_file(self, path: Path, exposure_s: float, iso: int) -> None:
        """Display a preview of the captured file."""
        loaded = False

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        # Try direct load first (works for JPEG)
        if not loaded:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
                self._image.set_pixbuf(pixbuf)
                self._stack.set_visible_child_name("image")
                loaded = True
            except Exception:
                pass

        # Try extracting embedded JPEG from CR2/RAW
        if not loaded and path.suffix.lower() in (".cr2", ".nef", ".arw", ".raw"):
            try:
                jpeg_bytes = _extract_embedded_jpeg(path)
                if jpeg_bytes:
                    loader = GdkPixbuf.PixbufLoader.new_with_type("jpeg")
                    loader.write(jpeg_bytes)
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    if pixbuf:
                        self._image.set_pixbuf(pixbuf)
                        self._stack.set_visible_child_name("image")
                        loaded = True
            except Exception:
                pass

        if not loaded:
            self._placeholder_label.set_label(f"Captured (no preview for {path.suffix})")
            self._stack.set_visible_child_name("placeholder")

        self._info_label.set_text(
            f"{path.name}  |  {exposure_s:.3g}s  |  ISO {iso}"
        )

    def clear(self) -> None:
        self._placeholder_label.set_label("No image captured yet")
        self._stack.set_visible_child_name("placeholder")
        self._info_label.set_text("")

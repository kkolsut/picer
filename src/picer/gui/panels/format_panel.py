"""File format panel: RAW / JPEG / RAW+JPEG selection."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from picer.camera.models import CameraConfig, CaptureFormat


class FormatPanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="File Format")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(8)
        row.set_margin_bottom(12)
        self.set_child(row)

        label = Gtk.Label(label="Format:")
        label.set_xalign(0)
        label.set_hexpand(True)
        row.append(label)

        self._combo = Gtk.ComboBoxText()
        for fmt in CaptureFormat:
            self._combo.append(fmt.name, fmt.label)
        # Default to RAW — always best for astronomy
        self._combo.set_active_id(CaptureFormat.RAW.name)
        row.append(self._combo)

    def get_format(self) -> CaptureFormat:
        return CaptureFormat[self._combo.get_active_id()]

    def apply_to_config(self, config: CameraConfig) -> None:
        config.capture_format = self.get_format()

    def set_from_config(self, config: CameraConfig) -> None:
        self._combo.set_active_id(config.capture_format.name)

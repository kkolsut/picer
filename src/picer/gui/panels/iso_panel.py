"""ISO panel: dropdown for ISO selection."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from picer.camera.models import ISO_VALUES, CameraConfig


class ISOPanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="ISO")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(8)
        row.set_margin_bottom(12)
        self.set_child(row)

        label = Gtk.Label(label="ISO:")
        label.set_xalign(0)
        label.set_hexpand(True)
        row.append(label)

        self._combo = Gtk.ComboBoxText()
        for iso in ISO_VALUES:
            self._combo.append(str(iso), str(iso))
        self._combo.set_active_id("400")
        row.append(self._combo)

    def get_iso(self) -> int:
        return int(self._combo.get_active_id())

    def apply_to_config(self, config: CameraConfig) -> None:
        config.iso = self.get_iso()

    def set_from_config(self, config: CameraConfig) -> None:
        self._combo.set_active_id(str(config.iso))

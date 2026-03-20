"""Exposure panel: shutter speed dropdown + bulb duration spinner."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from picer.camera.models import CameraConfig, ShutterSpeed


class ExposurePanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="Exposure")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(12)
        self.set_child(box)

        # Shutter speed row
        speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        speed_label = Gtk.Label(label="Shutter speed:")
        speed_label.set_xalign(0)
        speed_label.set_hexpand(True)
        speed_row.append(speed_label)

        self._speed_combo = Gtk.ComboBoxText()
        for speed in ShutterSpeed:
            label = speed.value if speed != ShutterSpeed.BULB else "BULB"
            self._speed_combo.append(speed.name, label)
        self._speed_combo.set_active_id(ShutterSpeed.S_1.name)
        self._speed_combo.connect("changed", self._on_speed_changed)
        speed_row.append(self._speed_combo)
        box.append(speed_row)

        # Bulb duration row (revealed when BULB is selected)
        self._bulb_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bulb_label = Gtk.Label(label="Duration (s):")
        bulb_label.set_xalign(0)
        bulb_label.set_hexpand(True)
        self._bulb_row.append(bulb_label)

        adjustment = Gtk.Adjustment(value=60, lower=1, upper=3600, step_increment=1, page_increment=60)
        self._bulb_spin = Gtk.SpinButton(adjustment=adjustment, climb_rate=1, digits=0)
        self._bulb_spin.set_numeric(True)
        self._bulb_row.append(self._bulb_spin)

        self._bulb_hint = Gtk.Label()
        self._bulb_hint.set_xalign(0)
        self._bulb_hint.add_css_class("dim-label")
        self._bulb_spin.connect("value-changed", self._update_bulb_hint)

        self._bulb_row.set_visible(False)
        box.append(self._bulb_row)
        box.append(self._bulb_hint)
        self._update_bulb_hint(self._bulb_spin)

    def _on_speed_changed(self, combo: Gtk.ComboBoxText) -> None:
        is_bulb = combo.get_active_id() == ShutterSpeed.BULB.name
        self._bulb_row.set_visible(is_bulb)
        self._bulb_hint.set_visible(is_bulb)

    def _update_bulb_hint(self, spin: Gtk.SpinButton) -> None:
        seconds = int(spin.get_value())
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        self._bulb_hint.set_text("  = " + " ".join(parts))

    def get_shutter_speed(self) -> ShutterSpeed:
        return ShutterSpeed[self._speed_combo.get_active_id()]

    def get_bulb_duration(self) -> float:
        return float(self._bulb_spin.get_value())

    def apply_to_config(self, config: CameraConfig) -> None:
        config.shutter_speed = self.get_shutter_speed()
        if config.shutter_speed == ShutterSpeed.BULB:
            config.bulb_duration_s = self.get_bulb_duration()

    def set_from_config(self, config: CameraConfig) -> None:
        self._speed_combo.set_active_id(config.shutter_speed.name)
        self._bulb_spin.set_value(config.bulb_duration_s)

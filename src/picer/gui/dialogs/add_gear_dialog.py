"""Dialog for adding a custom camera or optic."""
from __future__ import annotations

from typing import Callable, Literal
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from picer.gear.models import GearCamera, GearOptic
from picer.gear import store


def _labeled(label: str, widget: Gtk.Widget) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=label)
    lbl.set_width_chars(16)
    lbl.set_xalign(1.0)
    row.append(lbl)
    row.append(widget)
    return row


def _entry(placeholder: str = "") -> Gtk.Entry:
    e = Gtk.Entry()
    e.set_placeholder_text(placeholder)
    e.set_hexpand(True)
    return e


def _spin(lo: float, hi: float, step: float = 1.0, digits: int = 1) -> Gtk.SpinButton:
    adj = Gtk.Adjustment(value=0, lower=lo, upper=hi, step_increment=step)
    sb = Gtk.SpinButton(adjustment=adj, digits=digits)
    sb.set_hexpand(True)
    return sb


class AddGearDialog(Gtk.Window):
    """Modal window for adding a custom camera or optic."""

    def __init__(
        self,
        parent: Gtk.Window,
        mode: Literal["camera", "optic"],
        on_added: Callable[[], None],
    ) -> None:
        super().__init__()
        self._mode = mode
        self._on_added = on_added

        self.set_title("Add Custom Camera" if mode == "camera" else "Add Custom Optic")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.set_child(box)

        self._name = _entry("e.g. My Canon 6D")
        box.append(_labeled("Name:", self._name))

        if mode == "camera":
            self._sensor_w = _spin(1, 100, 0.1, 2)
            self._sensor_h = _spin(1, 100, 0.1, 2)
            self._pixels_x = _spin(100, 50000, 100, 0)
            self._pixels_y = _spin(100, 50000, 100, 0)
            self._pixel_um = _spin(0.1, 20, 0.01, 2)
            box.append(_labeled("Sensor W (mm):", self._sensor_w))
            box.append(_labeled("Sensor H (mm):", self._sensor_h))
            box.append(_labeled("Pixels X:", self._pixels_x))
            box.append(_labeled("Pixels Y:", self._pixels_y))
            box.append(_labeled("Pixel size (µm):", self._pixel_um))
        else:
            self._focal = _spin(1, 10000, 1, 1)
            self._aperture = _spin(1, 1000, 1, 1)
            box.append(_labeled("Focal length (mm):", self._focal))
            box.append(_labeled("Aperture (mm):", self._aperture))

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_margin_top(8)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _: self.close())
        btn_row.append(cancel)

        add = Gtk.Button(label="Add")
        add.add_css_class("suggested-action")
        add.connect("clicked", self._on_add)
        btn_row.append(add)

        box.append(btn_row)

    def _on_add(self, _btn: Gtk.Button) -> None:
        name = self._name.get_text().strip()
        if not name:
            return

        if self._mode == "camera":
            cam = GearCamera(
                name=name,
                sensor_w_mm=self._sensor_w.get_value(),
                sensor_h_mm=self._sensor_h.get_value(),
                pixels_x=int(self._pixels_x.get_value()),
                pixels_y=int(self._pixels_y.get_value()),
                pixel_um=self._pixel_um.get_value(),
                custom=True,
            )
            store.add_custom_camera(cam)
        else:
            optic = GearOptic(
                name=name,
                focal_mm=self._focal.get_value(),
                aperture_mm=self._aperture.get_value(),
                custom=True,
            )
            store.add_custom_optic(optic)

        self._on_added()
        self.close()

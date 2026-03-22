"""Gear panel: camera + optic selection with FOV and plate scale display."""
from __future__ import annotations

import math
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402

from picer.gear import store
from picer.gear.models import GearCamera, GearOptic


def _fov_plate(cam: GearCamera, optic: GearOptic) -> str:
    fov_w = math.degrees(2 * math.atan(cam.sensor_w_mm / (2 * optic.focal_mm)))
    fov_h = math.degrees(2 * math.atan(cam.sensor_h_mm / (2 * optic.focal_mm)))
    plate = 206.265 * cam.pixel_um / optic.focal_mm
    return f"FOV {fov_w:.2f}°×{fov_h:.2f}°  ·  {plate:.2f}\"/px"


class GearPanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="Gear")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(8)
        outer.set_margin_bottom(10)
        self.set_child(outer)

        # ── Camera row ────────────────────────────────────────────────
        cam_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cam_lbl = Gtk.Label(label="Camera:")
        cam_lbl.set_width_chars(7)
        cam_lbl.set_xalign(0)
        self._cam_combo = Gtk.ComboBoxText()
        self._cam_combo.set_hexpand(True)
        self._cam_combo.set_size_request(60, -1)
        self._cam_combo.get_cells()[0].set_property("ellipsize", Pango.EllipsizeMode.END)
        cam_add = Gtk.Button(label="+")
        cam_add.set_tooltip_text("Add custom camera")
        cam_add.connect("clicked", lambda _: self._open_add_dialog("camera"))
        cam_row.append(cam_lbl)
        cam_row.append(self._cam_combo)
        cam_row.append(cam_add)
        outer.append(cam_row)

        self._cam_info = Gtk.Label(label="")
        self._cam_info.set_xalign(0)
        self._cam_info.set_ellipsize(Pango.EllipsizeMode.END)
        self._cam_info.add_css_class("dim-label")
        outer.append(self._cam_info)

        # ── Optic row ─────────────────────────────────────────────────
        optic_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        optic_lbl = Gtk.Label(label="Optic:")
        optic_lbl.set_width_chars(7)
        optic_lbl.set_xalign(0)
        self._optic_combo = Gtk.ComboBoxText()
        self._optic_combo.set_hexpand(True)
        self._optic_combo.set_size_request(60, -1)
        self._optic_combo.get_cells()[0].set_property("ellipsize", Pango.EllipsizeMode.END)
        optic_add = Gtk.Button(label="+")
        optic_add.set_tooltip_text("Add custom optic")
        optic_add.connect("clicked", lambda _: self._open_add_dialog("optic"))
        optic_row.append(optic_lbl)
        optic_row.append(self._optic_combo)
        optic_row.append(optic_add)
        outer.append(optic_row)

        self._optic_info = Gtk.Label(label="")
        self._optic_info.set_xalign(0)
        self._optic_info.set_ellipsize(Pango.EllipsizeMode.END)
        self._optic_info.add_css_class("dim-label")
        outer.append(self._optic_info)

        # ── FOV / plate scale ─────────────────────────────────────────
        self._fov_label = Gtk.Label(label="")
        self._fov_label.set_xalign(0)
        self._fov_label.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(self._fov_label)

        # State
        self._cameras: list[GearCamera] = []
        self._optics: list[GearOptic] = []

        self._cam_combo.connect("changed", self._on_changed)
        self._optic_combo.connect("changed", self._on_changed)

        self._load()

    # ------------------------------------------------------------------

    def _load(self) -> None:
        cameras, optics, sel_cam, sel_optic = store.load_gear()
        self._cameras = cameras
        self._optics = optics

        self._cam_combo.handler_block_by_func(self._on_changed)
        self._optic_combo.handler_block_by_func(self._on_changed)

        # Rebuild camera dropdown
        while self._cam_combo.get_model() and self._cam_combo.get_model().iter_n_children(None) > 0:
            self._cam_combo.remove(0)
        for cam in cameras:
            self._cam_combo.append(cam.name, cam.name)

        # Rebuild optic dropdown
        while self._optic_combo.get_model() and self._optic_combo.get_model().iter_n_children(None) > 0:
            self._optic_combo.remove(0)
        for optic in optics:
            self._optic_combo.append(optic.name, optic.name)

        if sel_cam:
            self._cam_combo.set_active_id(sel_cam)
        elif cameras:
            self._cam_combo.set_active(0)

        if sel_optic:
            self._optic_combo.set_active_id(sel_optic)
        elif optics:
            self._optic_combo.set_active(0)

        self._cam_combo.handler_unblock_by_func(self._on_changed)
        self._optic_combo.handler_unblock_by_func(self._on_changed)

        self._update_labels()

    def _on_changed(self, _combo: Gtk.ComboBoxText) -> None:
        self._update_labels()
        store.save_selection(
            self._cam_combo.get_active_id(),
            self._optic_combo.get_active_id(),
        )

    def _update_labels(self) -> None:
        cam = self._selected_camera()
        optic = self._selected_optic()

        if cam:
            self._cam_info.set_text(
                f"{cam.sensor_w_mm}×{cam.sensor_h_mm} mm  ·  "
                f"{cam.pixels_x}×{cam.pixels_y} px  ·  {cam.pixel_um} µm"
            )
        else:
            self._cam_info.set_text("")

        if optic:
            self._optic_info.set_text(
                f"{optic.focal_mm:.0f} mm  f/{optic.f_ratio:.1f}"
            )
        else:
            self._optic_info.set_text("")

        if cam and optic:
            self._fov_label.set_text(_fov_plate(cam, optic))
        else:
            self._fov_label.set_text("")

    def _selected_camera(self) -> Optional[GearCamera]:
        name = self._cam_combo.get_active_id()
        return next((c for c in self._cameras if c.name == name), None)

    def _selected_optic(self) -> Optional[GearOptic]:
        name = self._optic_combo.get_active_id()
        return next((o for o in self._optics if o.name == name), None)

    def _open_add_dialog(self, mode: str) -> None:
        from picer.gui.dialogs.add_gear_dialog import AddGearDialog
        root = self.get_root()
        dlg = AddGearDialog(
            parent=root,
            mode=mode,
            on_added=self._load,
        )
        dlg.present()

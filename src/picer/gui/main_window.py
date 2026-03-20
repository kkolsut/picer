"""Main application window."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw  # noqa: E402
    _HAS_ADW = True
except (ValueError, ImportError):
    _HAS_ADW = False

from picer.camera.mock_backend import MockBackend
from picer.camera.models import BulbProgress, CameraConfig, CaptureResult, SequenceConfig
from picer.core.controller import CameraController
from picer.gui.panels.exposure_panel import ExposurePanel
from picer.gui.panels.format_panel import FormatPanel
from picer.gui.panels.iso_panel import ISOPanel
from picer.gui.panels.output_panel import OutputPanel
from picer.gui.panels.preview_panel import PreviewPanel
from picer.gui.panels.sequence_panel import SequencePanel

logger = logging.getLogger(__name__)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, controller: CameraController) -> None:
        super().__init__(application=app, title="Picer — Astronomy Capture")
        self.set_default_size(900, 650)

        self._controller = controller

        # ── Header bar ────────────────────────────────────────────────
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        self._connect_btn = Gtk.Button(label="Connect")
        self._connect_btn.connect("clicked", self._on_connect_clicked)
        header.pack_start(self._connect_btn)

        self._status_dot = Gtk.Label(label="⬤")
        self._status_dot.add_css_class("dim-label")
        self._status_dot.set_tooltip_text("Camera disconnected")
        header.pack_end(self._status_dot)

        # ── Layout: left settings + right preview ─────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(340)
        self.set_child(paned)

        # Left: scrollable settings column
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_width(280)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll.set_child(left_box)
        paned.set_start_child(scroll)

        # Panels
        self._exposure_panel = ExposurePanel()
        self._iso_panel = ISOPanel()
        self._format_panel = FormatPanel()
        self._sequence_panel = SequencePanel(
            on_start=self._on_sequence_start,
            on_stop=self._on_sequence_stop,
        )
        self._output_panel = OutputPanel()

        left_box.append(self._exposure_panel)
        left_box.append(self._iso_panel)
        left_box.append(self._format_panel)
        left_box.append(self._sequence_panel)
        left_box.append(self._output_panel)

        # Right: preview
        self._preview_panel = PreviewPanel()
        paned.set_end_child(self._preview_panel)
        paned.set_resize_start_child(False)
        paned.set_resize_end_child(True)

        # Update output panel filename preview whenever format/type changes
        self._format_panel._combo.connect("changed", self._on_settings_changed)
        self._exposure_panel._speed_combo.connect("changed", self._on_settings_changed)
        self._iso_panel._combo.connect("changed", self._on_settings_changed)
        self._sequence_panel._type_combo.connect("changed", self._on_settings_changed)

    # ------------------------------------------------------------------
    # Connect / disconnect
    # ------------------------------------------------------------------

    def _on_connect_clicked(self, _btn: Gtk.Button) -> None:
        if self._controller.is_connected():
            self._controller.disconnect()
            self._set_connected_state(False)
            return

        self._connect_btn.set_sensitive(False)
        self._connect_btn.set_label("Connecting…")

        def _worker() -> None:
            ok, msg = self._controller.connect()
            GLib.idle_add(self._on_connect_result, ok, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str) -> bool:
        self._connect_btn.set_sensitive(True)
        if ok:
            self._set_connected_state(True)
        else:
            self._connect_btn.set_label("Connect")
            self._show_error("Could not connect to camera", msg)
        return GLib.SOURCE_REMOVE

    def _set_connected_state(self, connected: bool) -> None:
        if connected:
            self._connect_btn.set_label("Disconnect")
            self._status_dot.remove_css_class("dim-label")
            self._status_dot.add_css_class("success")
            self._status_dot.set_tooltip_text("Camera connected")
        else:
            self._connect_btn.set_label("Connect")
            self._status_dot.remove_css_class("success")
            self._status_dot.add_css_class("dim-label")
            self._status_dot.set_tooltip_text("Camera disconnected")

    # ------------------------------------------------------------------
    # Settings → config
    # ------------------------------------------------------------------

    def _on_settings_changed(self, _widget: object) -> None:
        self._output_panel.update_config(
            self._build_camera_config(),
            self._sequence_panel.get_frame_type(),
        )

    def _build_camera_config(self) -> CameraConfig:
        config = CameraConfig()
        self._exposure_panel.apply_to_config(config)
        self._iso_panel.apply_to_config(config)
        self._format_panel.apply_to_config(config)
        return config

    def _build_sequence_config(self) -> SequenceConfig:
        camera_config = self._build_camera_config()
        seq_config = SequenceConfig(
            output_dir=self._output_panel.get_output_dir(),
            filename_template=self._output_panel.get_template(),
            camera_config=camera_config,
        )
        self._sequence_panel.apply_to_sequence_config(seq_config)
        return seq_config

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    def _on_sequence_start(self) -> None:
        if not self._controller.is_connected():
            self._show_error("Not connected", "Please connect to a camera first.")
            return

        seq_config = self._build_sequence_config()
        self._sequence_panel.set_running(True)

        self._controller.start_sequence(
            config=seq_config,
            on_frame_start=lambda idx, total: GLib.idle_add(
                self._sequence_panel.update_frame_progress, idx + 1, total
            ),
            on_frame_complete=lambda result: GLib.idle_add(
                self._on_frame_complete, result
            ),
            on_bulb_progress=lambda p: GLib.idle_add(
                self._sequence_panel.update_bulb_progress, p.elapsed_s, p.total_s
            ),
            on_error=lambda idx, exc: self._on_seq_error(idx, exc),
            on_sequence_complete=lambda results: GLib.idle_add(
                self._on_sequence_complete, results
            ),
            on_fits_ready=lambda result, paths: GLib.idle_add(
                self._preview_panel.show_fits,
                paths["G"],
                result.exposure_s,
                result.iso,
            ),
        )

    def _on_sequence_stop(self) -> None:
        self._controller.stop_sequence()
        self._sequence_panel.set_running(False)
        self._sequence_panel.set_status("Stopped")

    def _on_frame_complete(self, result: CaptureResult) -> bool:
        self._sequence_panel.set_status(f"Saved: {result.file_path.name}")
        self._preview_panel.show_file(result.file_path, result.exposure_s, result.iso)
        return GLib.SOURCE_REMOVE

    def _on_seq_error(self, idx: int, exc: Exception) -> bool:
        GLib.idle_add(
            self._sequence_panel.set_status, f"Frame {idx + 1} error: {exc}"
        )
        return True  # continue sequence on error

    def _on_sequence_complete(self, results: list[CaptureResult]) -> bool:
        self._sequence_panel.set_running(False)
        self._sequence_panel.set_status(f"Done — {len(results)} frame(s) captured")
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_error(self, title: str, message: str) -> None:
        dialog = Gtk.AlertDialog()
        dialog.set_message(title)
        dialog.set_detail(message)
        dialog.set_buttons(["OK"])
        dialog.show(self)

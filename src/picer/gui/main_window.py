"""Main application window."""
from __future__ import annotations

import logging
import tempfile
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

from picer.camera.models import CameraConfig, ObservationMetadata, SequenceConfig
from picer.core.api_client import APIClient
from picer.gui.panels.exposure_panel import ExposurePanel
from picer.gui.panels.format_panel import FormatPanel
from picer.gui.panels.gear_panel import GearPanel
from picer.gui.panels.iso_panel import ISOPanel
from picer.gui.panels.object_panel import ObjectPanel
from picer.gui.panels.output_panel import OutputPanel
from picer.gui.panels.preview_panel import PreviewPanel
from picer.gui.panels.sequence_panel import SequencePanel

logger = logging.getLogger(__name__)


class _FitsHeaderDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window, fits_path: Path) -> None:
        super().__init__()
        self.set_title(f"FITS Header — {fits_path.name}")
        self.set_transient_for(parent)
        self.set_default_size(700, 500)

        from astropy.io import fits as astrofits
        try:
            hdr = astrofits.getheader(str(fits_path))
            text = hdr.tostring(sep="\n", padding=False)
        except Exception as exc:
            text = f"Could not read header:\n{exc}"

        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_monospace(True)
        tv.get_buffer().set_text(text)

        sw = Gtk.ScrolledWindow()
        sw.set_child(tv)
        sw.set_vexpand(True)
        self.set_child(sw)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, client: APIClient) -> None:
        super().__init__(application=app, title="Picer — Astronomy Capture")
        self.set_default_size(900, 650)

        self._client = client
        self._current_fits_tmp: Optional[Path] = None  # tempfile for last downloaded FITS

        # ── Header bar ────────────────────────────────────────────────
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        self._connect_btn = Gtk.Button(label="Connect")
        css = Gtk.CssProvider()
        css.load_from_string("button { min-width: 110px; }")
        self._connect_btn.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._connect_btn.connect("clicked", self._on_connect_clicked)
        header.pack_start(self._connect_btn)

        self._status_dot = Gtk.Label()
        self._status_dot.set_markup('<span foreground="red">⬤</span>')
        self._status_dot.set_tooltip_text("Camera disconnected")
        header.pack_start(self._status_dot)

        # ── Layout: left settings + right preview ─────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(340)
        self.set_child(paned)

        # Left: tabbed settings column
        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        notebook.set_size_request(1, -1)
        paned.set_start_child(notebook)

        # Tab 1 — Capture
        capture_scroll = Gtk.ScrolledWindow()
        capture_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        capture_scroll.set_min_content_width(280)
        capture_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        capture_scroll.set_child(capture_box)
        notebook.append_page(capture_scroll, Gtk.Label(label="Capture"))

        # Tab 2 — Object
        object_scroll = Gtk.ScrolledWindow()
        object_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        object_scroll.set_min_content_width(280)
        object_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        object_scroll.set_child(object_box)
        notebook.insert_page(object_scroll, Gtk.Label(label="Object"), 1)

        # Tab 3 — Gear
        gear_scroll = Gtk.ScrolledWindow()
        gear_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        gear_scroll.set_min_content_width(280)
        gear_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        gear_scroll.set_child(gear_box)
        notebook.append_page(gear_scroll, Gtk.Label(label="Gear"))

        # Panels
        self._object_panel = ObjectPanel(client=client)
        self._gear_panel = GearPanel(client=client)
        self._exposure_panel = ExposurePanel()
        self._iso_panel = ISOPanel()
        self._format_panel = FormatPanel()
        self._sequence_panel = SequencePanel(
            on_start=self._on_sequence_start,
            on_stop=self._on_sequence_stop,
        )
        self._output_panel = OutputPanel()

        object_box.append(self._object_panel)
        gear_box.append(self._gear_panel)
        capture_box.append(self._exposure_panel)
        capture_box.append(self._iso_panel)
        capture_box.append(self._format_panel)
        capture_box.append(self._sequence_panel)
        capture_box.append(self._output_panel)

        self._fits_hdr_btn = Gtk.Button(label="FITS Header")
        self._fits_hdr_btn.set_sensitive(False)
        self._fits_hdr_btn.set_margin_start(8)
        self._fits_hdr_btn.set_margin_end(8)
        self._fits_hdr_btn.set_margin_top(4)
        self._fits_hdr_btn.set_margin_bottom(4)
        self._fits_hdr_btn.connect("clicked", self._on_show_fits_header)
        capture_box.append(self._fits_hdr_btn)

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
        if self._client.is_connected():
            self._client.disconnect()
            self._set_connected_state(False)
            return

        self._connect_btn.set_sensitive(False)
        self._connect_btn.set_label("Connecting…")
        self._status_dot.set_markup('<span foreground="yellow">⬤</span>')
        self._status_dot.set_tooltip_text("Connecting…")

        def _worker() -> None:
            ok, msg = self._client.connect()
            GLib.idle_add(self._on_connect_result, ok, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_connect_result(self, ok: bool, msg: str) -> bool:
        self._connect_btn.set_sensitive(True)
        if ok:
            self._set_connected_state(True)
        else:
            self._connect_btn.set_label("Connect")
            self._status_dot.set_markup('<span foreground="red">⬤</span>')
            self._status_dot.set_tooltip_text("Camera disconnected")
            self._show_error("Could not connect to camera", msg)
        return GLib.SOURCE_REMOVE

    def _set_connected_state(self, connected: bool) -> None:
        if connected:
            self._connect_btn.set_label("Disconnect")
            self._status_dot.set_markup('<span foreground="green">⬤</span>')
            self._status_dot.set_tooltip_text("Camera connected")
        else:
            self._connect_btn.set_label("Connect")
            self._status_dot.set_markup('<span foreground="red">⬤</span>')
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

    _FRAME_TYPE_LABEL = {"light": "object", "dark": "dark", "flat": "flat", "bias": "bias"}

    def _build_sequence_config(self) -> SequenceConfig:
        camera_config = self._build_camera_config()
        seq_config = SequenceConfig(
            output_dir=self._output_panel.get_output_dir(),
            filename_template=self._output_panel.get_template(),
            camera_config=camera_config,
        )
        self._sequence_panel.apply_to_sequence_config(seq_config)

        obj      = self._object_panel.get_current_object()
        lat, lon = self._object_panel.get_observer_location()
        cam      = self._gear_panel.get_selected_camera()
        optic    = self._gear_panel.get_selected_optic()
        seq_config.observation = ObservationMetadata(
            object_name  = obj.designation if obj else None,
            ra_deg       = obj.ra_deg   if obj   else None,
            dec_deg      = obj.dec_deg  if obj   else None,
            observer_lat = lat,
            observer_lon = lon,
            telescope    = optic.name        if optic else None,
            detector     = cam.name          if cam   else None,
            focal_mm     = optic.focal_mm    if optic else None,
            aperture_mm  = optic.aperture_mm if optic else None,
            pixel_um     = cam.pixel_um      if cam   else None,
            frame_type   = self._FRAME_TYPE_LABEL.get(seq_config.frame_type.value, "unknown"),
        )
        return seq_config

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    def _on_sequence_start(self) -> None:
        if not self._client.is_connected():
            self._show_error("Not connected", "Please connect to a camera first.")
            return

        seq_config = self._build_sequence_config()
        self._sequence_panel.set_running(True)

        self._client.start_sequence(
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
            # API mode: on_fits_ready receives (capture_id, exposure_s, iso)
            on_fits_ready=lambda capture_id, exposure_s, iso: threading.Thread(
                target=self._download_fits_and_show,
                args=(capture_id, exposure_s, iso),
                daemon=True,
            ).start(),
        )

    def _on_sequence_stop(self) -> None:
        self._client.stop_sequence()
        self._sequence_panel.set_running(False)
        self._sequence_panel.set_status("Stopped")

    def _download_fits_and_show(
        self, capture_id: str, exposure_s: float, iso: int
    ) -> None:
        """Download G-channel FITS from server, write to tempfile, show in UI."""
        try:
            data = self._client.download_fits_channel(capture_id, "G")
        except Exception as exc:
            logger.warning("FITS download failed for %s: %s", capture_id, exc)
            return

        try:
            fd, path_str = tempfile.mkstemp(suffix=".fits", prefix="picer_")
            tmp_path = Path(path_str)
            import os
            with os.fdopen(fd, "wb") as f:
                f.write(data)
        except Exception as exc:
            logger.warning("Could not write FITS tempfile: %s", exc)
            return

        GLib.idle_add(self._on_fits_downloaded, tmp_path, exposure_s, iso)

    def _on_fits_downloaded(
        self, tmp_path: Path, exposure_s: float, iso: int
    ) -> bool:
        # Clean up previous tempfile
        if self._current_fits_tmp and self._current_fits_tmp.exists():
            try:
                self._current_fits_tmp.unlink()
            except Exception:
                pass
        self._current_fits_tmp = tmp_path
        self._preview_panel.show_fits(tmp_path, exposure_s, iso)
        self._fits_hdr_btn.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _on_show_fits_header(self, _btn: Gtk.Button) -> None:
        path = self._preview_panel.get_current_fits_path()
        if path is None:
            return
        _FitsHeaderDialog(self, path).present()

    def _on_frame_complete(self, result) -> bool:
        self._sequence_panel.set_status(f"Saved: {result.file_path.name}")
        # Show a "converting" placeholder while waiting for fits_ready
        self._preview_panel.show_file(result.file_path, result.exposure_s, result.iso)
        return GLib.SOURCE_REMOVE

    def _on_seq_error(self, idx: int, exc: Exception) -> bool:
        if isinstance(exc, ValueError):
            GLib.idle_add(self._sequence_panel.set_running, False)
            GLib.idle_add(self._show_error, f"Frame {idx + 1} failed", str(exc))
            return False  # stop sequence
        GLib.idle_add(
            self._sequence_panel.set_status, f"Frame {idx + 1} error: {exc}"
        )
        return True  # continue sequence on transient errors

    def _on_sequence_complete(self, results: list) -> bool:
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

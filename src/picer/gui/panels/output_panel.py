"""Output panel: save directory, filename template."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from picer.camera.models import CameraConfig
from picer.utils.file_naming import preview_filename


class OutputPanel(Gtk.Frame):
    def __init__(self) -> None:
        super().__init__(label="Output")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(12)
        self.set_child(box)

        # Directory
        dir_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dir_label = Gtk.Label(label="Save to:")
        dir_label.set_xalign(0)
        dir_label.set_width_chars(9)
        dir_row.append(dir_label)

        default_dir = str(Path.home() / "picer_captures")
        self._dir_entry = Gtk.Entry()
        self._dir_entry.set_text(default_dir)
        self._dir_entry.set_hexpand(True)
        self._dir_entry.connect("changed", self._on_template_changed)
        dir_row.append(self._dir_entry)

        browse_btn = Gtk.Button(label="…")
        browse_btn.set_tooltip_text("Browse for output directory")
        browse_btn.connect("clicked", self._on_browse_clicked)
        dir_row.append(browse_btn)
        box.append(dir_row)

        # Filename template
        tmpl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tmpl_label = Gtk.Label(label="Filename:")
        tmpl_label.set_xalign(0)
        tmpl_label.set_width_chars(9)
        tmpl_row.append(tmpl_label)

        self._tmpl_entry = Gtk.Entry()
        self._tmpl_entry.set_text("picer_{date}_{seq:04d}")
        self._tmpl_entry.set_hexpand(True)
        self._tmpl_entry.set_placeholder_text("picer_{date}_{seq:04d}")
        self._tmpl_entry.connect("changed", self._on_template_changed)
        tmpl_row.append(self._tmpl_entry)
        box.append(tmpl_row)

        # Preview label
        self._preview_label = Gtk.Label()
        self._preview_label.set_xalign(0)
        self._preview_label.add_css_class("dim-label")
        box.append(self._preview_label)

        self._current_config: Optional[CameraConfig] = None
        self._update_preview()

    def _on_browse_clicked(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Select output directory")
        dialog.select_folder(
            parent=self.get_root(),  # type: ignore[arg-type]
            cancellable=None,
            callback=self._on_folder_selected,
        )

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: GLib.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._dir_entry.set_text(folder.get_path() or "")
        except GLib.Error:
            pass

    def _on_template_changed(self, _widget: Gtk.Widget) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        if self._current_config is None:
            from picer.camera.models import CameraConfig
            cfg = CameraConfig()
        else:
            cfg = self._current_config
        try:
            name = preview_filename(self.get_template(), cfg)
            self._preview_label.set_text(f"→ {name}")
        except Exception:
            self._preview_label.set_text("(invalid template)")

    def update_config(self, config: CameraConfig) -> None:
        self._current_config = config
        self._update_preview()

    def get_output_dir(self) -> Path:
        return Path(self._dir_entry.get_text() or str(Path.home() / "picer_captures"))

    def get_template(self) -> str:
        return self._tmpl_entry.get_text() or "picer_{date}_{seq:04d}"

"""Dialog for selecting and downloading captures from the server."""
from __future__ import annotations

import datetime
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

if TYPE_CHECKING:
    from picer.core.api_client import APIClient

logger = logging.getLogger(__name__)


class DownloadDialog(Gtk.Window):
    """
    Browse all CR2+FITS files on the server, select what to download.

    Each row represents one CR2 capture.  Global toggles choose whether
    to download RAW (CR2) and/or FITS (all available channels).
    """

    def __init__(
        self,
        parent: Gtk.Window,
        client: "APIClient",
        dest_dir: Path,
        on_done: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__()
        self.set_title("Download from Server")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(620, 500)

        self._client = client
        self._on_done = on_done
        # capture_id/name -> (check_button, entry_dict)
        self._rows: dict[str, tuple[Gtk.CheckButton, dict]] = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        # ── Server directory bar ──────────────────────────────────────
        dir_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dir_bar.set_margin_start(12)
        dir_bar.set_margin_end(12)
        dir_bar.set_margin_top(10)
        dir_bar.set_margin_bottom(4)

        srv_lbl = Gtk.Label(label="Server dir:")
        srv_lbl.set_xalign(0)
        dir_bar.append(srv_lbl)

        self._server_dir_entry = Gtk.Entry()
        self._server_dir_entry.set_placeholder_text("default (~/ picer_captures)")
        self._server_dir_entry.set_hexpand(True)
        dir_bar.append(self._server_dir_entry)

        scan_btn = Gtk.Button(label="Scan")
        scan_btn.add_css_class("suggested-action")
        scan_btn.connect("clicked", lambda _: self._load())
        dir_bar.append(scan_btn)

        root.append(dir_bar)

        # ── Toolbar: select-all / deselect-all / count ────────────────
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_bottom(4)

        sel_all = Gtk.Button(label="Select All")
        sel_all.connect("clicked", lambda _: self._set_all(True))
        toolbar.append(sel_all)

        sel_none = Gtk.Button(label="Deselect All")
        sel_none.connect("clicked", lambda _: self._set_all(False))
        toolbar.append(sel_none)

        self._count_label = Gtk.Label(label="")
        self._count_label.set_hexpand(True)
        self._count_label.set_xalign(1.0)
        self._count_label.add_css_class("dim-label")
        toolbar.append(self._count_label)

        root.append(toolbar)

        # ── Capture list ──────────────────────────────────────────────
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_margin_start(12)
        sw.set_margin_end(12)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        sw.set_child(self._list_box)
        root.append(sw)

        sep = Gtk.Separator()
        sep.set_margin_top(8)
        root.append(sep)

        # ── Bottom options ────────────────────────────────────────────
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.set_margin_top(8)
        bottom.set_margin_bottom(10)

        # What to download
        what_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        what_lbl = Gtk.Label(label="Download:")
        what_lbl.set_width_chars(9)
        what_lbl.set_xalign(0)
        what_row.append(what_lbl)
        self._include_raw = Gtk.CheckButton(label="RAW (CR2)")
        self._include_raw.set_active(True)
        what_row.append(self._include_raw)
        self._include_fits = Gtk.CheckButton(label="FITS (R, G, B channels)")
        self._include_fits.set_active(True)
        what_row.append(self._include_fits)
        bottom.append(what_row)

        # Output directory
        out_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        out_lbl = Gtk.Label(label="Save to:")
        out_lbl.set_width_chars(9)
        out_lbl.set_xalign(0)
        self._dir_entry = Gtk.Entry()
        self._dir_entry.set_text(str(dest_dir))
        self._dir_entry.set_hexpand(True)
        browse_btn = Gtk.Button(label="…")
        browse_btn.set_tooltip_text("Browse for output directory")
        browse_btn.connect("clicked", self._on_browse)
        out_row.append(out_lbl)
        out_row.append(self._dir_entry)
        out_row.append(browse_btn)
        bottom.append(out_row)

        self._delete_check = Gtk.CheckButton(label="Delete from server after download")
        bottom.append(self._delete_check)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("dim-label")
        bottom.append(self._status_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_margin_top(4)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda _: self.close())
        btn_row.append(close_btn)

        self._download_btn = Gtk.Button(label="Download")
        self._download_btn.add_css_class("suggested-action")
        self._download_btn.set_sensitive(False)
        self._download_btn.connect("clicked", self._on_download)
        btn_row.append(self._download_btn)

        bottom.append(btn_row)
        root.append(bottom)

        self._load()

    # ------------------------------------------------------------------
    # Load / populate
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._count_label.set_text("Scanning…")
        self._download_btn.set_sensitive(False)
        self._clear_list()
        server_dir = self._server_dir_entry.get_text().strip() or None
        threading.Thread(target=self._do_load, args=(server_dir,), daemon=True).start()

    def _do_load(self, server_dir: Optional[str]) -> None:
        try:
            result = self._client.list_server_files(server_dir)
        except Exception as exc:
            GLib.idle_add(self._count_label.set_text, f"Error: {exc}")
            return
        GLib.idle_add(self._populate, result)

    def _populate(self, result: dict) -> bool:
        files = result.get("files", [])
        scanned_dir = result.get("dir", "")
        if not self._server_dir_entry.get_text().strip():
            self._server_dir_entry.set_placeholder_text(scanned_dir)
        for entry in files:
            self._add_row(entry)
        n = len(files)
        self._count_label.set_text(f"{n} capture{'s' if n != 1 else ''} found")
        self._update_download_btn()
        return GLib.SOURCE_REMOVE

    def _clear_list(self) -> None:
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)
        self._rows.clear()

    def _add_row(self, entry: dict) -> None:
        row = Gtk.ListBoxRow()
        row.set_activatable(False)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox.set_margin_start(8)
        hbox.set_margin_end(8)
        hbox.set_margin_top(6)
        hbox.set_margin_bottom(6)

        check = Gtk.CheckButton()
        check.connect("toggled", lambda _: self._update_download_btn())
        hbox.append(check)

        name_lbl = Gtk.Label(label=entry.get("name", ""))
        name_lbl.set_xalign(0)
        name_lbl.set_hexpand(True)
        name_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        hbox.append(name_lbl)

        # FITS badge
        fits_chs = entry.get("fits_channels", [])
        fits_txt = f"FITS: {'·'.join(fits_chs)}" if fits_chs else "FITS: —"
        fits_lbl = Gtk.Label(label=fits_txt)
        fits_lbl.add_css_class("dim-label" if not fits_chs else "")
        hbox.append(fits_lbl)

        # Timestamp
        mtime = entry.get("mtime")
        if mtime:
            try:
                ts_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = ""
        else:
            ts_str = ""
        time_lbl = Gtk.Label(label=ts_str)
        time_lbl.add_css_class("dim-label")
        hbox.append(time_lbl)

        row.set_child(hbox)
        self._list_box.append(row)
        self._rows[entry["raw_path"]] = (check, entry)

    # ------------------------------------------------------------------

    def _set_all(self, active: bool) -> None:
        for check, _ in self._rows.values():
            check.set_active(active)

    def _selected_entries(self) -> list[dict]:
        return [entry for _, (check, entry) in self._rows.items() if check.get_active()]

    def _update_download_btn(self) -> None:
        n = len(self._selected_entries())
        if n:
            self._download_btn.set_label(f"Download ({n})")
            self._download_btn.set_sensitive(True)
        else:
            self._download_btn.set_label("Download")
            self._download_btn.set_sensitive(False)

    def _on_browse(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Select output directory")
        dialog.select_folder(parent=self, cancellable=None, callback=self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: GLib.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._dir_entry.set_text(folder.get_path() or "")
        except GLib.Error:
            pass

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_download(self, _btn: Gtk.Button) -> None:
        entries = self._selected_entries()
        if not entries:
            return
        dest = Path(self._dir_entry.get_text() or str(Path.home()))
        include_raw = self._include_raw.get_active()
        include_fits = self._include_fits.get_active()
        delete_after = self._delete_check.get_active()

        if not include_raw and not include_fits:
            self._status_label.set_text("Select at least RAW or FITS to download.")
            return

        self._download_btn.set_sensitive(False)
        self._status_label.set_text("Starting download…")
        threading.Thread(
            target=self._do_download,
            args=(entries, dest, include_raw, include_fits, delete_after),
            daemon=True,
        ).start()

    def _do_download(
        self,
        entries: list[dict],
        dest: Path,
        include_raw: bool,
        include_fits: bool,
        delete_after: bool,
    ) -> None:
        ok = 0
        total_files = 0
        try:
            dest.mkdir(parents=True, exist_ok=True)
            total_files = sum(
                (1 if include_raw else 0)
                + (len(e.get("fits_channels", [])) if include_fits else 0)
                for e in entries
            )
            done = 0

            for entry in entries:
                paths_to_fetch: list[str] = []
                if include_raw:
                    paths_to_fetch.append(entry["raw_path"])
                if include_fits:
                    for ch in entry.get("fits_channels", []):
                        fp = entry.get("fits_paths", {}).get(ch)
                        if fp:
                            paths_to_fetch.append(fp)

                for server_path in paths_to_fetch:
                    done += 1
                    GLib.idle_add(
                        self._status_label.set_text,
                        f"Downloading {done}/{total_files}: {Path(server_path).name}",
                    )
                    try:
                        data, filename = self._client.download_file_path(server_path)
                        (dest / filename).write_bytes(data)
                        ok += 1
                        logger.info("Saved %s to %s", filename, dest)
                    except Exception as exc:
                        logger.warning("Download failed for %s: %s", server_path, exc)
                        GLib.idle_add(
                            self._status_label.set_text,
                            f"Error: {Path(server_path).name}: {exc}",
                        )

                if delete_after:
                    paths_to_delete = [entry["raw_path"]] + list(
                        entry.get("fits_paths", {}).values()
                    )
                    for p in paths_to_delete:
                        try:
                            self._client.delete_file_path(p)
                        except Exception as exc:
                            logger.warning("Delete failed for %s: %s", p, exc)

        except Exception as exc:
            logger.error("Download thread error: %s", exc)
            GLib.idle_add(self._status_label.set_text, f"Error: {exc}")

        GLib.idle_add(self._on_done_main, ok, total_files, delete_after)

    def _on_done_main(self, ok: int, total: int, deleted: bool) -> bool:
        self._status_label.set_text(f"Downloaded {ok}/{total} file(s)")
        if self._on_done:
            self._on_done(ok)
        if deleted:
            self._load()
        else:
            self._update_download_btn()
        return GLib.SOURCE_REMOVE

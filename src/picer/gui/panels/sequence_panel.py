"""Sequence panel: frame count, interval, progress, start/stop."""
from __future__ import annotations

from typing import Callable, Optional
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from picer.camera.models import SequenceConfig


class SequencePanel(Gtk.Frame):
    def __init__(
        self,
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(label="Sequence")
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(4)

        self._on_start = on_start
        self._on_stop = on_stop
        self._running = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(12)
        self.set_child(box)

        # Frame count
        frames_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        frames_label = Gtk.Label(label="Frames:")
        frames_label.set_xalign(0)
        frames_label.set_hexpand(True)
        frames_row.append(frames_label)
        adj = Gtk.Adjustment(value=1, lower=1, upper=9999, step_increment=1, page_increment=10)
        self._frames_spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        frames_row.append(self._frames_spin)
        box.append(frames_row)

        # Interval
        interval_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        interval_label = Gtk.Label(label="Interval (s):")
        interval_label.set_xalign(0)
        interval_label.set_hexpand(True)
        interval_row.append(interval_label)
        adj2 = Gtk.Adjustment(value=0, lower=0, upper=3600, step_increment=1, page_increment=60)
        self._interval_spin = Gtk.SpinButton(adjustment=adj2, climb_rate=1, digits=1)
        interval_row.append(self._interval_spin)
        box.append(interval_row)

        # Progress bar (hidden when idle)
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_visible(False)
        box.append(self._progress_bar)

        # Bulb sub-progress bar
        self._bulb_bar = Gtk.ProgressBar()
        self._bulb_bar.set_show_text(True)
        self._bulb_bar.set_visible(False)
        box.append(self._bulb_bar)

        # Status label
        self._status_label = Gtk.Label(label="")
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("dim-label")
        box.append(self._status_label)

        # Start / Stop button
        self._start_btn = Gtk.Button(label="Start Sequence")
        self._start_btn.add_css_class("suggested-action")
        self._start_btn.connect("clicked", self._on_button_clicked)
        box.append(self._start_btn)

    # ------------------------------------------------------------------
    # UI events
    # ------------------------------------------------------------------

    def _on_button_clicked(self, _btn: Gtk.Button) -> None:
        if self._running:
            if self._on_stop:
                self._on_stop()
        else:
            if self._on_start:
                self._on_start()

    # ------------------------------------------------------------------
    # State updates (called from main thread via GLib.idle_add)
    # ------------------------------------------------------------------

    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._start_btn.set_label("Stop")
            self._start_btn.remove_css_class("suggested-action")
            self._start_btn.add_css_class("destructive-action")
            self._progress_bar.set_visible(True)
        else:
            self._start_btn.set_label("Start Sequence")
            self._start_btn.remove_css_class("destructive-action")
            self._start_btn.add_css_class("suggested-action")
            self._progress_bar.set_visible(False)
            self._bulb_bar.set_visible(False)
            self._status_label.set_text("")

    def update_frame_progress(self, current: int, total: int) -> None:
        fraction = current / total if total > 0 else 0
        self._progress_bar.set_fraction(fraction)
        self._progress_bar.set_text(f"Frame {current}/{total}")

    def update_bulb_progress(self, elapsed_s: float, total_s: float) -> None:
        self._bulb_bar.set_visible(True)
        fraction = min(1.0, elapsed_s / total_s) if total_s > 0 else 0
        self._bulb_bar.set_fraction(fraction)
        remaining = max(0.0, total_s - elapsed_s)
        self._bulb_bar.set_text(f"Exposure: {elapsed_s:.0f}s / {total_s:.0f}s  ({remaining:.0f}s left)")

    def set_status(self, text: str) -> None:
        self._status_label.set_text(text)

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_frame_count(self) -> int:
        return int(self._frames_spin.get_value())

    def get_interval(self) -> float:
        return float(self._interval_spin.get_value())

    def apply_to_sequence_config(self, config: SequenceConfig) -> None:
        config.frame_count = self.get_frame_count()
        config.interval_s = self.get_interval()

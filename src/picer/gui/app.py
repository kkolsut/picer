"""GTK application entry point."""
from __future__ import annotations

import logging
import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from picer.core.controller import CameraController
from picer.gui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _make_controller(use_mock: bool) -> CameraController:
    if use_mock:
        from picer.camera.mock_backend import MockBackend
        backend = MockBackend(sim_speed=0.05)
    else:
        try:
            from picer.camera.gphoto2_backend import GPhoto2Backend
            backend = GPhoto2Backend()
        except ImportError:
            logger.warning("python-gphoto2 not installed — using mock backend")
            from picer.camera.mock_backend import MockBackend
            backend = MockBackend(sim_speed=0.05)
    return CameraController(backend)


class PicerApp(Gtk.Application):
    def __init__(self, use_mock: bool = False) -> None:
        super().__init__(
            application_id="org.picer.Picer",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._use_mock = use_mock
        self._controller: CameraController | None = None

    def do_activate(self) -> None:
        win = self.get_active_window()
        if win is None:
            self._controller = _make_controller(self._use_mock)
            win = MainWindow(app=self, controller=self._controller)
        win.present()

    def do_shutdown(self) -> None:
        if self._controller and self._controller.is_connected():
            self._controller.disconnect()
        Gtk.Application.do_shutdown(self)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    use_mock = "--mock" in (argv or sys.argv)
    app = PicerApp(use_mock=use_mock)
    return app.run(argv or sys.argv)

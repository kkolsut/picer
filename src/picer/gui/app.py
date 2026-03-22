"""GTK application entry point."""
from __future__ import annotations

import logging
import os
import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from picer.core.api_client import APIClient
from picer.gui.main_window import MainWindow

logger = logging.getLogger(__name__)

_DEFAULT_SERVER = os.environ.get("PICER_SERVER_URL", "http://localhost:8765")
_DEFAULT_USER = os.environ.get("PICER_USER", "picer")
_DEFAULT_PASS = os.environ.get("PICER_PASSWORD", "")


class PicerApp(Gtk.Application):
    def __init__(self, server_url: str, username: str, password: str) -> None:
        super().__init__(
            application_id="org.picer.Picer",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._server_url = server_url
        self._username = username
        self._password = password
        self._client: APIClient | None = None

    def do_activate(self) -> None:
        win = self.get_active_window()
        if win is None:
            self._client = APIClient(
                base_url=self._server_url,
                username=self._username,
                password=self._password,
            )
            win = MainWindow(app=self, client=self._client)
        win.present()

    def do_shutdown(self) -> None:
        if self._client and self._client.is_connected():
            self._client.disconnect()
        Gtk.Application.do_shutdown(self)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv
    level = logging.DEBUG if "--debug" in args else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    # Parse --server URL
    server_url = _DEFAULT_SERVER
    for i, arg in enumerate(args):
        if arg == "--server" and i + 1 < len(args):
            server_url = args[i + 1]
        elif arg.startswith("--server="):
            server_url = arg.split("=", 1)[1]

    app = PicerApp(
        server_url=server_url,
        username=_DEFAULT_USER,
        password=_DEFAULT_PASS,
    )
    return app.run(args)

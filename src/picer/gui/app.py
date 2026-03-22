"""GTK application entry point."""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk  # noqa: E402

from picer.core.api_client import APIClient
from picer.gui.main_window import MainWindow

logger = logging.getLogger(__name__)

_DEFAULT_USER = os.environ.get("PICER_USER", "picer")
_DEFAULT_PASS = os.environ.get("PICER_PASSWORD", "")


def _start_embedded_server(port: int) -> None:
    """Run uvicorn in-process. Called from a daemon thread."""
    import uvicorn

    uvicorn.run(
        "picer.api.app:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


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

    # Determine server URL and whether to start an embedded server.
    # Explicit --server arg or PICER_SERVER_URL env var → connect to that server.
    # Nothing provided → start an embedded server automatically.
    explicit_url: str | None = None
    for i, arg in enumerate(args):
        if arg == "--server" and i + 1 < len(args):
            explicit_url = args[i + 1]
        elif arg.startswith("--server="):
            explicit_url = arg.split("=", 1)[1]

    env_url = os.environ.get("PICER_SERVER_URL")

    if explicit_url:
        server_url = explicit_url
        embedded = False
    elif env_url:
        server_url = env_url
        embedded = False
    else:
        server_url = "http://127.0.0.1:8765"
        embedded = True

    if embedded:
        port = int(server_url.rsplit(":", 1)[-1])
        t = threading.Thread(target=_start_embedded_server, args=(port,), daemon=True)
        t.start()
        logger.info("Embedded API server starting on %s …", server_url)

        # Poll before entering the GTK main loop (up to 3 s).
        tmp = APIClient(base_url=server_url)
        for _ in range(30):
            ok, _ = tmp.check_reachable()
            if ok:
                logger.info("Embedded server ready")
                break
            time.sleep(0.1)
        else:
            logger.warning(
                "Embedded server did not become ready in 3 s — continuing anyway"
            )

    app = PicerApp(
        server_url=server_url,
        username=_DEFAULT_USER,
        password=_DEFAULT_PASS,
    )
    return app.run(args)

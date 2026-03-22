"""FastAPI application factory and CLI entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from picer.api import state
from picer.api.routes import camera, capture, files, gear, objects, sequence

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Give the event bus a reference to the running asyncio loop so camera
    # daemon threads can post events into it.
    state.event_bus.set_loop(asyncio.get_event_loop())
    logger.info("Picer API server ready")
    yield
    # Graceful shutdown
    if state.controller.is_connected():
        state.controller.disconnect()
    logger.info("Picer API server stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Picer API",
        description="Astronomy DSLR capture server for Canon EOS cameras",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(camera.router)
    app.include_router(capture.router)
    app.include_router(sequence.router)
    app.include_router(gear.router)
    app.include_router(objects.router)
    app.include_router(files.router)

    return app


app = create_app()


def main() -> None:
    """Entry point for the `picer-api` CLI command."""
    import argparse

    parser = argparse.ArgumentParser(description="Picer API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    import uvicorn

    uvicorn.run(
        "picer.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )

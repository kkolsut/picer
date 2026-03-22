"""Global server-side singletons shared across all request handlers."""
from __future__ import annotations

from picer.api.captures import CaptureRegistry
from picer.api.events import SequenceEventBus
from picer.api.session import SessionManager
from picer.camera.gphoto2_backend import GPhoto2Backend
from picer.core.controller import CameraController

_backend = GPhoto2Backend()
controller = CameraController(_backend)
captures = CaptureRegistry()
event_bus = SequenceEventBus()
session = SessionManager(on_timeout=controller.disconnect)

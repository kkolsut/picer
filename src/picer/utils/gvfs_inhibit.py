"""Utilities to detect and remove GVFS auto-mounts that block libgphoto2."""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def gvfs_is_blocking_camera() -> bool:
    """Return True if gvfs has mounted a gphoto2 camera."""
    try:
        result = subprocess.run(
            ["gio", "mount", "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "gphoto2" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_gvfs_camera_uri() -> str | None:
    """Return the exact gphoto2 mount URI from gio, or None if not found.

    gio mount --list outputs lines like:
      Mount(0): Canon Digital Camera -> gphoto2://Canon_Inc._Canon_Digital_Camera/
    """
    try:
        result = subprocess.run(
            ["gio", "mount", "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "gphoto2://" in line and "->" in line:
                # Extract the URI after the arrow
                uri = line.split("->")[-1].strip()
                return uri
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def unmount_gvfs_camera() -> bool:
    """Attempt to unmount any gphoto2 GVFS mount. Return True on success."""
    uri = _get_gvfs_camera_uri() or "gphoto2://"
    try:
        result = subprocess.run(
            ["gio", "mount", "--unmount", uri],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info("GVFS camera mount removed")
            import time
            time.sleep(1.5)  # wait for gvfsd to fully release the USB device
            return True
        logger.warning("Failed to unmount GVFS: %s", result.stderr.strip())
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not run gio: %s", exc)
        return False


def ensure_camera_accessible() -> tuple[bool, str]:
    """
    Check for GVFS conflict and attempt to resolve it.
    Returns (ok, message). If ok is False the caller should show message to user.
    """
    if not gvfs_is_blocking_camera():
        return True, ""

    logger.warning("GVFS has mounted the camera — attempting to unmount")
    if unmount_gvfs_camera():
        return True, ""

    msg = (
        "GVFS has auto-mounted the camera and picer could not remove the mount.\n\n"
        "Run the following command and try again:\n"
        "    gio mount --unmount gphoto2://\n\n"
        "To prevent this permanently, install the udev rule:\n"
        "    sudo cp udev/99-picer-camera.rules /etc/udev/rules.d/\n"
        "    sudo udevadm control --reload-rules\n"
        "Then unplug and replug the camera."
    )
    return False, msg

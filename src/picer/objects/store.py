"""Persistent storage for selected DSO and observer location.

File: ~/.config/picer/observer.json
Schema:
{
  "selected_catalog": "M",
  "selected_designation": "M 42",
  "observer_lat": 48.8566,
  "observer_lon": 2.3522
}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "picer" / "observer.json"


def _load_raw() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as exc:
        logger.warning("Could not read observer.json: %s", exc)
        return {}


def _save_raw(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def load_observer() -> tuple[Optional[str], Optional[str], Optional[float], Optional[float]]:
    """Return (selected_catalog, selected_designation, lat, lon).

    All values may be None if not yet persisted.
    """
    data = _load_raw()
    return (
        data.get("selected_catalog"),
        data.get("selected_designation"),
        data.get("observer_lat"),
        data.get("observer_lon"),
    )


def save_selection(catalog: Optional[str], designation: Optional[str]) -> None:
    data = _load_raw()
    data["selected_catalog"] = catalog
    data["selected_designation"] = designation
    _save_raw(data)


def save_location(lat: Optional[float], lon: Optional[float]) -> None:
    data = _load_raw()
    data["observer_lat"] = lat
    data["observer_lon"] = lon
    _save_raw(data)


def load_favorites() -> list[dict]:
    """Return list of {name, lat, lon} dicts, empty list if none."""
    return _load_raw().get("favorites", [])


def add_favorite(name: str, lat: float, lon: float) -> None:
    data = _load_raw()
    favs = data.get("favorites", [])
    favs = [f for f in favs if f["name"] != name]  # replace if same name
    favs.append({"name": name, "lat": lat, "lon": lon})
    data["favorites"] = favs
    _save_raw(data)


def remove_favorite(name: str) -> None:
    data = _load_raw()
    data["favorites"] = [f for f in data.get("favorites", []) if f["name"] != name]
    _save_raw(data)

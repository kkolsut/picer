"""DSO catalog, observer location, and favorites endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import picer.objects.store as obj_store
from picer.api.auth import require_auth
from picer.objects.catalog import CATALOG_KEYS, catalog_label, find_object
from picer.objects.models import DeepSkyObject

router = APIRouter(prefix="/objects", tags=["objects"])


class SelectionBody(BaseModel):
    catalog: str | None = None
    designation: str | None = None


class LocationBody(BaseModel):
    lat: float
    lon: float


class FavoriteBody(BaseModel):
    name: str
    lat: float
    lon: float


# ── Catalogs ──────────────────────────────────────────────────────────────────

@router.get("/catalogs")
def list_catalogs(user: Annotated[str, Depends(require_auth)]):
    """List all available catalog keys with human-readable labels."""
    return {
        "catalogs": [
            {"key": k, "label": catalog_label(k)} for k in CATALOG_KEYS
        ]
    }


@router.get("/search")
def search_objects(
    catalog: Annotated[str, Query(description="Catalog key, e.g. NGC")],
    q: Annotated[str, Query(description="Object number, designation, or name substring")],
    user: Annotated[str, Depends(require_auth)],
):
    """Search a catalog. Returns the first matching DSO or 404."""
    if catalog not in CATALOG_KEYS:
        raise HTTPException(400, f"Unknown catalog '{catalog}'. Valid: {CATALOG_KEYS}")

    obj = find_object(catalog, q)
    if obj is None:
        raise HTTPException(404, f"No object found for '{q}' in catalog {catalog}")

    return _dso_dict(obj)


# ── Selection ─────────────────────────────────────────────────────────────────

@router.get("/selection")
def get_selection(user: Annotated[str, Depends(require_auth)]):
    catalog, designation, _, _ = obj_store.load_observer()
    return {"catalog": catalog, "designation": designation}


@router.put("/selection")
def set_selection(body: SelectionBody, user: Annotated[str, Depends(require_auth)]):
    obj_store.save_selection(body.catalog, body.designation)
    return {"catalog": body.catalog, "designation": body.designation}


# ── Observer location ─────────────────────────────────────────────────────────

@router.get("/location")
def get_location(user: Annotated[str, Depends(require_auth)]):
    _, _, lat, lon = obj_store.load_observer()
    return {"lat": lat, "lon": lon}


@router.put("/location")
def set_location(body: LocationBody, user: Annotated[str, Depends(require_auth)]):
    obj_store.save_location(body.lat, body.lon)
    return {"lat": body.lat, "lon": body.lon}


# ── Favorites ─────────────────────────────────────────────────────────────────

@router.get("/favorites")
def list_favorites(user: Annotated[str, Depends(require_auth)]):
    return {"favorites": obj_store.load_favorites()}


@router.post("/favorites", status_code=201)
def add_favorite(body: FavoriteBody, user: Annotated[str, Depends(require_auth)]):
    obj_store.add_favorite(body.name, body.lat, body.lon)
    return {"name": body.name, "lat": body.lat, "lon": body.lon}


@router.delete("/favorites/{name}", status_code=204)
def delete_favorite(name: str, user: Annotated[str, Depends(require_auth)]):
    obj_store.remove_favorite(name)


# ── Helper ────────────────────────────────────────────────────────────────────

def _dso_dict(obj: DeepSkyObject) -> dict:
    return {
        "catalog": obj.catalog,
        "designation": obj.designation,
        "name": obj.name,
        "obj_type": obj.obj_type,
        "constellation": obj.constellation,
        "ra_deg": obj.ra_deg,
        "dec_deg": obj.dec_deg,
    }

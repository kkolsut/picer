"""Filesystem file-browser endpoints — scan capture directories and download files."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from picer.api.auth import require_auth

router = APIRouter(prefix="/files", tags=["files"])

_ALLOWED_SUFFIXES = {".cr2", ".fits"}
_DEFAULT_DIR = Path.home() / "picer_captures"


@router.get("")
def list_files(
    dir: Annotated[str | None, Query()] = None,
    user: Annotated[str, Depends(require_auth)] = "",
):
    """
    Scan a directory for CR2 captures and their associated FITS files.

    Returns one entry per CR2 file found (recursively), with a list of
    available FITS channel names (R, G, B) detected by filename convention.
    """
    base = Path(dir).expanduser() if dir else _DEFAULT_DIR
    if not base.exists():
        return {"dir": str(base), "files": []}

    entries = []
    for raw_path in sorted(base.rglob("*.cr2"), key=lambda p: p.stat().st_mtime):
        stem = raw_path.stem
        parent = raw_path.parent
        fits_channels = [
            ch for ch in ("R", "G", "B")
            if (parent / f"{stem}_{ch}.fits").exists()
        ]
        stat = raw_path.stat()
        entries.append({
            "name": stem,
            "raw_path": str(raw_path),
            "raw_size": stat.st_size,
            "fits_channels": fits_channels,
            "fits_paths": {
                ch: str(parent / f"{stem}_{ch}.fits")
                for ch in fits_channels
            },
            "mtime": stat.st_mtime,
        })

    return {"dir": str(base), "files": entries}


@router.get("/download")
def download_file(
    path: Annotated[str, Query()],
    user: Annotated[str, Depends(require_auth)] = "",
):
    """Download any CR2 or FITS file by absolute server path."""
    p = Path(path)
    if p.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(403, "File type not allowed")
    if not p.exists():
        raise HTTPException(404, "File not found on server")
    return FileResponse(p, media_type="application/octet-stream", filename=p.name)


@router.delete("/delete", status_code=204)
def delete_file(
    path: Annotated[str, Query()],
    user: Annotated[str, Depends(require_auth)] = "",
):
    """Delete a CR2 or FITS file from the server by absolute path."""
    p = Path(path)
    if p.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise HTTPException(403, "File type not allowed")
    if not p.exists():
        return  # already gone — treat as success
    try:
        p.unlink()
    except Exception as exc:
        raise HTTPException(500, f"Could not delete file: {exc}")

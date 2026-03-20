"""Filename template engine for captured images."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from picer.camera.models import CameraConfig, CaptureFormat

# Tokens supported in filename templates.
# {date}       → 2026-03-15
# {time}       → 235930
# {datetime}   → 2026-03-15T235930
# {seq}        → frame index (supports format spec, e.g. {seq:04d})
# {iso}        → ISO value
# {exp}        → exposure in seconds (e.g. 180s or 0.004s)
# {camera}     → "450D"

_TOKEN_RE = re.compile(r"\{(\w+)(?::([^}]+))?\}")


def render_filename(
    template: str,
    config: CameraConfig,
    seq: int,
    camera_model: str = "450D",
    now: datetime | None = None,
) -> str:
    """Render a filename template to a string (without extension)."""
    if now is None:
        now = datetime.now()

    tokens: dict[str, object] = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H%M%S"),
        "datetime": now.strftime("%Y-%m-%dT%H%M%S"),
        "seq": seq,
        "iso": config.iso,
        "exp": f"{config.effective_exposure_s:.3g}s",
        "camera": camera_model,
    }

    def replace(m: re.Match) -> str:
        key = m.group(1)
        fmt = m.group(2)
        value = tokens.get(key, m.group(0))  # leave unknown tokens as-is
        if fmt and isinstance(value, int):
            return format(value, fmt)
        return str(value)

    return _TOKEN_RE.sub(replace, template)


def build_output_path(
    output_dir: Path,
    template: str,
    config: CameraConfig,
    seq: int,
    camera_model: str = "450D",
    now: datetime | None = None,
) -> Path:
    """Return the full output path including extension."""
    stem = render_filename(template, config, seq, camera_model, now)
    ext = config.capture_format.extension
    return output_dir / f"{stem}{ext}"


def preview_filename(template: str, config: CameraConfig, seq: int = 1) -> str:
    """Return an example rendered filename for UI preview."""
    stem = render_filename(template, config, seq)
    ext = config.capture_format.extension
    return f"{stem}{ext}"

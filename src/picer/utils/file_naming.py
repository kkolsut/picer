"""Filename template engine for captured images."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from picer.camera.models import CameraConfig, CaptureFormat, FrameType

# Tokens supported in filename templates.
# {date}       → 2026-03-15
# {time}       → 235930
# {datetime}   → 2026-03-15T235930
# {seq}        → frame index (supports format spec, e.g. {seq:04d})
# {type}       → frame type: light, dark, flat, bias
# {iso}        → ISO value
# {exp}        → exposure in seconds (e.g. 180s or 0.004s)
# {camera}     → "450D"

_TOKEN_RE = re.compile(r"\{(\w+)(?::([^}]+))?\}")

_TOKEN_PATTERNS = {
    "date": r"\d{4}-\d{2}-\d{2}",
    "time": r"\d{6}",
    "datetime": r"\d{4}-\d{2}-\d{2}T\d{6}",
    "type": r"(?:light|dark|flat|bias)",
    "iso": r"\d+",
    "exp": r"[\d.]+s",
    "camera": r".+",
}


def _template_to_seq_regex(template: str, frame_type: FrameType | None = None) -> re.Pattern | None:
    """Convert a filename template to a regex that captures the {seq} number.

    If *frame_type* is given, ``{type}`` matches only that specific value so
    that e.g. dark frames are counted separately from light frames.

    Returns None if the template contains no {seq} token.
    """
    has_seq = False
    result = ""
    last_end = 0

    for m in _TOKEN_RE.finditer(template):
        result += re.escape(template[last_end : m.start()])
        key = m.group(1)
        if key == "seq":
            has_seq = True
            result += r"(\d+)"
        elif key == "type" and frame_type is not None:
            result += re.escape(frame_type.value)
        else:
            pat = _TOKEN_PATTERNS.get(key, r".+")
            result += f"(?:{pat})"
        last_end = m.end()

    result += re.escape(template[last_end:])

    if not has_seq:
        return None
    return re.compile(f"^{result}$")


def find_next_seq(
    output_dir: Path,
    template: str,
    extension: str,
    frame_type: FrameType = FrameType.LIGHT,
) -> int:
    """Return the next sequence number to use, skipping any already in *output_dir*.

    Scans *output_dir* for files whose stems match *template* (with *extension*)
    and the given *frame_type*, then returns ``max_existing_seq + 1``.  Each
    frame type maintains its own independent counter.  Returns 1 when the
    directory is empty, does not exist, or the template has no ``{seq}`` token.
    """
    pattern = _template_to_seq_regex(template, frame_type)
    if pattern is None or not output_dir.exists():
        return 1

    max_seq = 0
    for f in output_dir.iterdir():
        if f.suffix.lower() != extension.lower():
            continue
        m = pattern.match(f.stem)
        if m:
            max_seq = max(max_seq, int(m.group(1)))

    return max_seq + 1


def render_filename(
    template: str,
    config: CameraConfig,
    seq: int,
    camera_model: str = "450D",
    now: datetime | None = None,
    frame_type: FrameType = FrameType.LIGHT,
) -> str:
    """Render a filename template to a string (without extension)."""
    if now is None:
        now = datetime.now()

    tokens: dict[str, object] = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H%M%S"),
        "datetime": now.strftime("%Y-%m-%dT%H%M%S"),
        "seq": seq,
        "type": frame_type.value,
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
    frame_type: FrameType = FrameType.LIGHT,
) -> Path:
    """Return the full output path including extension."""
    stem = render_filename(template, config, seq, camera_model, now, frame_type)
    ext = config.capture_format.extension
    return output_dir / f"{stem}{ext}"


def preview_filename(
    template: str,
    config: CameraConfig,
    seq: int = 1,
    frame_type: FrameType = FrameType.LIGHT,
) -> str:
    """Return an example rendered filename for UI preview."""
    stem = render_filename(template, config, seq, frame_type=frame_type)
    ext = config.capture_format.extension
    return f"{stem}{ext}"

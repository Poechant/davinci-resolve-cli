"""Timecode ↔ frame conversion.

Non-drop only — DaVinciResolveScript exposes no public DF arithmetic anyway.
"""
from __future__ import annotations

import re


TC_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})[:;](\d{1,2})$")


def parse_timecode(tc: str, fps: float) -> int:
    if fps <= 0:
        raise ValueError("fps must be positive")
    m = TC_RE.match(tc.strip())
    if not m:
        raise ValueError(f"invalid timecode (expected HH:MM:SS:FF): {tc!r}")
    h, mn, s, f = (int(x) for x in m.groups())
    fps_int = int(round(fps))
    if f >= fps_int:
        raise ValueError(f"frame component {f} >= fps {fps_int}")
    return (h * 3600 + mn * 60 + s) * fps_int + f


def frame_to_timecode(frame: int, fps: float) -> str:
    if fps <= 0:
        raise ValueError("fps must be positive")
    if frame < 0:
        raise ValueError("frame must be non-negative")
    fps_int = int(round(fps))
    total_seconds, f = divmod(frame, fps_int)
    h, rem = divmod(total_seconds, 3600)
    mn, s = divmod(rem, 60)
    return f"{h:02d}:{mn:02d}:{s:02d}:{f:02d}"

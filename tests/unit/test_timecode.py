"""Timecode arithmetic."""
from __future__ import annotations

import pytest

from dvr.timecode import frame_to_timecode, parse_timecode


@pytest.mark.parametrize(
    "tc,fps,frame",
    [
        ("00:00:00:00", 24, 0),
        ("00:00:01:00", 24, 24),
        ("00:00:01:12", 24, 36),
        ("01:00:00:00", 24, 86400),
        ("00:01:00:00", 30, 1800),
        ("00:00:00:14", 30, 14),
    ],
)
def test_parse_timecode(tc: str, fps: float, frame: int) -> None:
    assert parse_timecode(tc, fps) == frame


@pytest.mark.parametrize(
    "tc",
    ["00:00:00", "not-a-tc", "00:00:00:30", "1:2:3:4:5"],
)
def test_parse_timecode_invalid(tc: str) -> None:
    with pytest.raises(ValueError):
        parse_timecode(tc, 24)


def test_parse_timecode_requires_positive_fps() -> None:
    with pytest.raises(ValueError):
        parse_timecode("00:00:01:00", 0)


@pytest.mark.parametrize(
    "frame,fps,expected",
    [
        (0, 24, "00:00:00:00"),
        (24, 24, "00:00:01:00"),
        (36, 24, "00:00:01:12"),
        (86400, 24, "01:00:00:00"),
        (1800, 30, "00:01:00:00"),
    ],
)
def test_frame_to_timecode(frame: int, fps: float, expected: str) -> None:
    assert frame_to_timecode(frame, fps) == expected


def test_round_trip() -> None:
    for fr in [0, 1, 99, 1234, 86399]:
        assert parse_timecode(frame_to_timecode(fr, 24), 24) == fr


def test_frame_to_timecode_rejects_negative() -> None:
    with pytest.raises(ValueError):
        frame_to_timecode(-1, 24)

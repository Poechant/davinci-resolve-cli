"""AC12 / AC13 / AC14 (収敛: marker only) / AC15 — timeline + dry-run."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.commands import project as proj_cmd
from dvr.commands import timeline as tl_cmd
from dvr.errors import NotFound, ValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "timeline.json"


def _schemas() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture
def ready(fake_client, fake_resolve):
    proj_cmd.new_project(fake_client, "demo")
    return fake_client


# ---------- list / current / open / new ----------

def test_list_empty(ready) -> None:
    assert tl_cmd.list_timelines(ready) == []


def test_new_then_list(ready) -> None:
    out = tl_cmd.new_timeline(ready, "Main")
    assert out["ok"] is True
    items = tl_cmd.list_timelines(ready)
    assert len(items) == 1
    assert items[0]["name"] == "Main"
    jsonschema.validate(items, _schemas()["$defs"]["TimelineList"])


def test_new_sets_fps(ready) -> None:
    out = tl_cmd.new_timeline(ready, "Cinema", fps=23.976)
    assert pytest.approx(out["fps"], abs=0.01) == 23.976


def test_new_empty_name_raises(ready) -> None:
    with pytest.raises(ValidationError):
        tl_cmd.new_timeline(ready, "   ")


def test_current_without_timeline_raises(ready) -> None:
    with pytest.raises(ValidationError):
        tl_cmd.current_timeline(ready)


def test_current_after_new(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    assert tl_cmd.current_timeline(ready) == {"name": "Main", "fps": 24.0}


def test_open_unknown_raises(ready) -> None:
    with pytest.raises(NotFound):
        tl_cmd.open_timeline(ready, "ghost")


def test_open_existing(ready) -> None:
    tl_cmd.new_timeline(ready, "A")
    tl_cmd.new_timeline(ready, "B")
    assert tl_cmd.open_timeline(ready, "A") == {"ok": True, "name": "A"}
    assert tl_cmd.current_timeline(ready)["name"] == "A"


# ---------- clips ----------

def test_clips_empty(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    assert tl_cmd.list_clips_in_timeline(ready) == []


def test_clips_returns_track_metadata(ready, fake_resolve) -> None:
    from tests.conftest import FakeTimelineItem
    tl_cmd.new_timeline(ready, "Main")
    proj = fake_resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    item = FakeTimelineItem("shot01", start=0, end=48)
    tl._add_track_item("video", 1, item)
    out = tl_cmd.list_clips_in_timeline(ready)
    assert len(out) == 1
    row = out[0]
    assert row["trackType"] == "video"
    assert row["trackIndex"] == 1
    assert row["frames"]["start"] == 0 and row["frames"]["end"] == 48
    assert row["start"] == "00:00:00:00"
    assert row["end"] == "00:00:02:00"
    jsonschema.validate(out, _schemas()["$defs"]["ClipsInTimeline"])


def test_clips_unknown_timeline_raises(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    with pytest.raises(NotFound):
        tl_cmd.list_clips_in_timeline(ready, timeline_name="ghost")


# ---------- marker add ----------

def test_marker_add_inserts_record(ready, fake_resolve) -> None:
    tl_cmd.new_timeline(ready, "Main")
    out = tl_cmd.add_marker(ready, at="00:00:01:00", note="cue", color="Green")
    assert out["ok"] is True
    assert out["frame"] == 24
    jsonschema.validate(out, _schemas()["$defs"]["MarkerAction"])
    proj = fake_resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert 24 in tl.GetMarkers()


def test_marker_add_invalid_color_raises(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    with pytest.raises(ValidationError):
        tl_cmd.add_marker(ready, at="00:00:01:00", color="Periwinkle")


def test_marker_add_invalid_tc_raises(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    with pytest.raises(ValueError):
        tl_cmd.add_marker(ready, at="bogus")


def test_marker_add_duplicate_raises(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    tl_cmd.add_marker(ready, at="00:00:01:00", color="Red")
    from dvr.errors import ApiCallFailed
    with pytest.raises(ApiCallFailed):
        tl_cmd.add_marker(ready, at="00:00:01:00", color="Red")


# ---------- marker delete ----------

def test_marker_delete(ready, fake_resolve) -> None:
    tl_cmd.new_timeline(ready, "Main")
    tl_cmd.add_marker(ready, at="00:00:01:00", color="Blue")
    out = tl_cmd.delete_marker(ready, at="00:00:01:00")
    assert out["ok"] is True
    proj = fake_resolve.GetProjectManager().GetCurrentProject()
    assert 24 not in proj.GetCurrentTimeline().GetMarkers()


def test_marker_delete_missing_raises(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    with pytest.raises(NotFound):
        tl_cmd.delete_marker(ready, at="00:00:05:00")


# ---------- marker list ----------

def test_marker_list_empty(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    assert tl_cmd.list_markers(ready) == []


def test_marker_list_sorted(ready) -> None:
    tl_cmd.new_timeline(ready, "Main")
    tl_cmd.add_marker(ready, at="00:00:03:00", color="Red")
    tl_cmd.add_marker(ready, at="00:00:01:00", color="Blue")
    out = tl_cmd.list_markers(ready)
    assert [m["frame"] for m in out] == [24, 72]
    assert out[0]["timecode"] == "00:00:01:00"


# ---------- dry-run ----------

def test_marker_add_dry_run_does_not_mutate(ready, fake_resolve) -> None:
    tl_cmd.new_timeline(ready, "Main")
    out = tl_cmd.add_marker(ready, at="00:00:01:00", color="Blue", dry_run=True)
    jsonschema.validate(out, _schemas()["$defs"]["DryRun"])
    assert out["planned"][0]["action"] == "marker.add"
    proj = fake_resolve.GetProjectManager().GetCurrentProject()
    assert proj.GetCurrentTimeline().GetMarkers() == {}


def test_marker_delete_dry_run_does_not_mutate(ready, fake_resolve) -> None:
    tl_cmd.new_timeline(ready, "Main")
    tl_cmd.add_marker(ready, at="00:00:01:00", color="Blue")
    out = tl_cmd.delete_marker(ready, at="00:00:01:00", dry_run=True)
    jsonschema.validate(out, _schemas()["$defs"]["DryRun"])
    proj = fake_resolve.GetProjectManager().GetCurrentProject()
    # marker still there
    assert 24 in proj.GetCurrentTimeline().GetMarkers()

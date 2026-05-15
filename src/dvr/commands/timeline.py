"""`dvr timeline ...` — timeline management + marker ops.

NOTE on v0.1 scope: cut/move have no public Resolve Python API and are
deferred to v0.2 (see context append on 2026-05-14). Only marker ops are
exposed as mutating commands here.
"""
from __future__ import annotations

from typing import Any, Optional

import typer

from ..errors import ApiCallFailed, NotFound, ValidationError
from ..output import emit, resolve_format
from ..resolve import ResolveClient
from ..timecode import frame_to_timecode, parse_timecode
from ..wi_client import WIBridge, default_bridge
from . import _client as client_mod

app = typer.Typer(help="Timeline management and marker operations.")
marker_app = typer.Typer(help="Marker operations on the current timeline.")
app.add_typer(marker_app, name="marker")


VALID_MARKER_COLORS = {
    "Blue", "Cyan", "Green", "Yellow", "Red", "Pink",
    "Purple", "Fuchsia", "Rose", "Lavender", "Sky",
    "Mint", "Lemon", "Sand", "Cocoa", "Cream",
}


def _current_project_or_raise(client: ResolveClient):
    proj = client.project_manager().GetCurrentProject()
    if proj is None:
        raise ValidationError("no project is currently open")
    return proj


def _fps_of(timeline) -> float:
    fps_str = timeline.GetSetting("timelineFrameRate") or "24"
    try:
        return float(fps_str)
    except ValueError:
        return 24.0


# ---------- pure helpers ----------

def list_timelines(client: ResolveClient) -> list[dict[str, Any]]:
    proj = _current_project_or_raise(client)
    count = int(proj.GetTimelineCount() or 0)
    out: list[dict[str, Any]] = []
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl is None:
            continue
        out.append({"index": i, "name": tl.GetName(), "fps": _fps_of(tl)})
    return out


def current_timeline(client: ResolveClient) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    tl = proj.GetCurrentTimeline()
    if tl is None:
        raise ValidationError("no timeline is currently selected")
    return {"name": tl.GetName(), "fps": _fps_of(tl)}


def open_timeline(client: ResolveClient, name: str) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    count = int(proj.GetTimelineCount() or 0)
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl is not None and tl.GetName() == name:
            if not proj.SetCurrentTimeline(tl):
                raise ApiCallFailed("SetCurrentTimeline", name)
            return {"ok": True, "name": name}
    raise NotFound("Timeline", name)


def delete_timeline(
    client: ResolveClient,
    name: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a timeline by name. Resolves to a MediaPool.DeleteTimelines() call."""
    if not name.strip():
        raise ValidationError("timeline name must not be empty")
    proj = _current_project_or_raise(client)
    count = int(proj.GetTimelineCount() or 0)
    target = None
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl is not None and tl.GetName() == name:
            target = tl
            break
    if target is None:
        raise NotFound("Timeline", name)
    if dry_run:
        return {"dryRun": True, "planned": [{"action": "timeline.delete", "name": name}]}
    mp = proj.GetMediaPool()
    if not mp.DeleteTimelines([target]):
        raise ApiCallFailed("DeleteTimelines", name)
    return {"ok": True, "name": name}


def new_timeline(
    client: ResolveClient, name: str, *, fps: Optional[float] = None
) -> dict[str, Any]:
    if not name.strip():
        raise ValidationError("timeline name must not be empty")
    proj = _current_project_or_raise(client)
    if fps is not None and fps > 0:
        # framerate is a project-level setting that locks once a timeline exists
        proj.SetSetting("timelineFrameRate", str(fps))
    mp = proj.GetMediaPool()
    tl = mp.CreateEmptyTimeline(name)
    if tl is None:
        raise ApiCallFailed("CreateEmptyTimeline", name)
    return {"ok": True, "name": name, "fps": _fps_of(tl)}


def _resolve_target_timeline(proj, timeline_name: Optional[str]):
    if timeline_name in (None, "", "cur", "current"):
        tl = proj.GetCurrentTimeline()
        if tl is None:
            raise ValidationError("no timeline is currently selected")
        return tl
    count = int(proj.GetTimelineCount() or 0)
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        if tl is not None and tl.GetName() == timeline_name:
            return tl
    raise NotFound("Timeline", timeline_name)


def list_clips_in_timeline(
    client: ResolveClient, timeline_name: Optional[str] = None
) -> list[dict[str, Any]]:
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    out: list[dict[str, Any]] = []
    for track_type in ("video", "audio", "subtitle"):
        track_count = int(tl.GetTrackCount(track_type) or 0)
        for idx in range(1, track_count + 1):
            items = tl.GetItemListInTrack(track_type, idx) or []
            for item in items:
                start_frame = int(item.GetStart() or 0)
                end_frame = int(item.GetEnd() or 0)
                source = None
                src = item.GetMediaPoolItem()
                if src is not None:
                    source = {"id": src.GetMediaId(), "name": src.GetName()}
                out.append(
                    {
                        "trackType": track_type,
                        "trackIndex": idx,
                        "name": item.GetName(),
                        "start": frame_to_timecode(start_frame, fps),
                        "end": frame_to_timecode(end_frame, fps),
                        "frames": {"start": start_frame, "end": end_frame},
                        "source": source,
                    }
                )
    return out


def add_marker(
    client: ResolveClient,
    *,
    at: str,
    note: str = "",
    name: str = "",
    color: str = "Blue",
    duration: int = 1,
    timeline_name: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if color not in VALID_MARKER_COLORS:
        raise ValidationError(
            f"invalid marker color: {color}",
            hint=f"Valid colors: {', '.join(sorted(VALID_MARKER_COLORS))}",
        )
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    frame = parse_timecode(at, fps)
    if dry_run:
        return {
            "dryRun": True,
            "planned": [
                {
                    "action": "marker.add",
                    "frame": frame,
                    "timecode": at,
                    "color": color,
                    "name": name,
                    "note": note,
                    "duration": duration,
                }
            ],
        }
    if not tl.AddMarker(frame, color, name, note, duration):
        raise ApiCallFailed("AddMarker", at)
    return {"ok": True, "frame": frame, "timecode": at}


def delete_marker(
    client: ResolveClient,
    *,
    at: str,
    timeline_name: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    frame = parse_timecode(at, fps)
    if dry_run:
        return {
            "dryRun": True,
            "planned": [{"action": "marker.delete", "frame": frame, "timecode": at}],
        }
    if not tl.DeleteMarkerAtFrame(frame):
        raise NotFound("Marker", at)
    return {"ok": True, "frame": frame, "timecode": at}


def cut_at(
    client: ResolveClient,
    *,
    at: str,
    timeline_name: Optional[str] = None,
    dry_run: bool = False,
    bridge: Optional[WIBridge] = None,
) -> dict[str, Any]:
    """Cut the timeline at a given timecode.

    DaVinciResolveScript Python API has no razor-cut primitive, so we delegate
    to the WI plugin. The v0.2 WI implementation drops a marker as a cut
    proposal — true SplitClip is queued for v0.3 (see CHANGELOG).
    """
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    frame = parse_timecode(at, fps)
    if dry_run:
        return {
            "dryRun": True,
            "planned": [
                {"action": "timeline.cut", "frame": frame, "timecode": at, "via": "workflow_integrations"}
            ],
        }
    out = (bridge or default_bridge()).call("timeline.cut", {"at": at})
    if isinstance(out, dict):
        return {"ok": True, "frame": frame, "timecode": at, **out}
    return {"ok": True, "frame": frame, "timecode": at}


def move_clip(
    client: ResolveClient,
    *,
    clip_id: str,
    to: str,
    timeline_name: Optional[str] = None,
    dry_run: bool = False,
    bridge: Optional[WIBridge] = None,
) -> dict[str, Any]:
    """Move a clip within a timeline to a new start timecode.

    Same caveat as `cut_at`: delegated to WI; v0.2 returns the WI plugin's
    structured "deferred" payload while we wait for an API surface to land.
    """
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    frame = parse_timecode(to, fps)
    if dry_run:
        return {
            "dryRun": True,
            "planned": [
                {
                    "action": "timeline.move",
                    "clipId": clip_id,
                    "to": to,
                    "frame": frame,
                    "via": "workflow_integrations",
                }
            ],
        }
    out = (bridge or default_bridge()).call("timeline.move", {"clipId": clip_id, "to": to})
    return {"ok": True, "clipId": clip_id, "frame": frame, "timecode": to, **(out if isinstance(out, dict) else {})}


def list_markers(
    client: ResolveClient, timeline_name: Optional[str] = None
) -> list[dict[str, Any]]:
    proj = _current_project_or_raise(client)
    tl = _resolve_target_timeline(proj, timeline_name)
    fps = _fps_of(tl)
    markers = tl.GetMarkers() or {}
    rows: list[dict[str, Any]] = []
    for frame in sorted(markers.keys()):
        info = markers[frame]
        rows.append(
            {
                "frame": int(frame),
                "timecode": frame_to_timecode(int(frame), fps),
                "color": info.get("color"),
                "name": info.get("name", ""),
                "note": info.get("note", ""),
                "duration": int(info.get("duration", 1)),
            }
        )
    return rows


# ---------- typer wrappers ----------

@app.command("list")
def cli_list(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """List timelines in the current project."""
    emit(list_timelines(client_mod.get()), resolve_format(fmt))


@app.command("current")
def cli_current(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Show the currently selected timeline."""
    emit(current_timeline(client_mod.get()), resolve_format(fmt))


@app.command("open")
def cli_open(name: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Switch to a timeline by name."""
    emit(open_timeline(client_mod.get(), name), resolve_format(fmt))


@app.command("new")
def cli_new(
    name: str,
    fps: Optional[float] = typer.Option(None, "--fps"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Create a new empty timeline."""
    emit(new_timeline(client_mod.get(), name, fps=fps), resolve_format(fmt))


@app.command("delete")
def cli_delete(
    name: str,
    dry_run: bool = typer.Option(False, "--dry-run"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Delete a timeline by name."""
    emit(delete_timeline(client_mod.get(), name, dry_run=dry_run), resolve_format(fmt))


@app.command("clips")
def cli_clips(
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """List clips on a timeline (current by default)."""
    emit(list_clips_in_timeline(client_mod.get(), timeline_name=timeline), resolve_format(fmt))


@marker_app.command("add")
def cli_marker_add(
    at: str = typer.Option(..., "--at", help="Timecode HH:MM:SS:FF"),
    note: str = typer.Option("", "--note"),
    name: str = typer.Option("", "--name"),
    color: str = typer.Option("Blue", "--color", "-c"),
    duration: int = typer.Option(1, "--duration", "-d"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Add a marker at a timecode."""
    emit(
        add_marker(
            client_mod.get(),
            at=at, note=note, name=name, color=color,
            duration=duration, timeline_name=timeline, dry_run=dry_run,
        ),
        resolve_format(fmt),
    )


@marker_app.command("delete")
def cli_marker_delete(
    at: str = typer.Option(..., "--at"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Delete a marker at a timecode."""
    emit(
        delete_marker(
            client_mod.get(),
            at=at, timeline_name=timeline, dry_run=dry_run,
        ),
        resolve_format(fmt),
    )


@marker_app.command("list")
def cli_marker_list(
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """List markers on a timeline."""
    emit(list_markers(client_mod.get(), timeline_name=timeline), resolve_format(fmt))


@app.command("cut")
def cli_cut(
    at: str = typer.Option(..., "--at", help="Timecode HH:MM:SS:FF"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Cut the timeline at <TC>. Requires the WI plugin (run `dvr install-wi` first)."""
    emit(
        cut_at(client_mod.get(), at=at, timeline_name=timeline, dry_run=dry_run),
        resolve_format(fmt),
    )


@app.command("move")
def cli_move(
    clip_id: str = typer.Option(..., "--clip", help="Clip id (from `dvr timeline clips`)"),
    to: str = typer.Option(..., "--to", help="Target start timecode HH:MM:SS:FF"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Move a clip within the timeline. Requires the WI plugin."""
    emit(
        move_clip(client_mod.get(), clip_id=clip_id, to=to, timeline_name=timeline, dry_run=dry_run),
        resolve_format(fmt),
    )

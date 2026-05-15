"""Pytest fixtures.

`fake_resolve` provides an in-memory state machine that mimics enough of the
DaVinciResolveScript surface to unit-test commands without launching Resolve.
It is intentionally **not** exhaustive — subsequent tasks (T2-T5) extend it.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import pytest


# ---------- minimal fake graph ----------

_NEXT_CLIP_ID = [0]


def _next_clip_id() -> str:
    _NEXT_CLIP_ID[0] += 1
    return f"clip-{_NEXT_CLIP_ID[0]:04d}"


class FakeMediaPoolItem:
    def __init__(self, name: str, props: Optional[dict[str, Any]] = None) -> None:
        self._name = name
        self._id = _next_clip_id()
        defaults = {
            "Resolution": "1920x1080",
            "Duration": "00:00:10:00",
            "Format": "QuickTime",
            "FPS": "24",
            "Type": "Video",
        }
        defaults.update(props or {})
        self._props = defaults
        self._flags: list[str] = []
        self._metadata: dict[str, str] = {}

    def GetName(self) -> str:
        return self._name

    def GetMediaId(self) -> str:
        return self._id

    def GetClipProperty(self, key: Optional[str] = None) -> Any:
        return self._props if key is None else self._props.get(key, "")

    def SetClipProperty(self, key: str, value: str) -> bool:
        self._props[key] = value
        return True

    def AddFlag(self, color: str) -> bool:
        self._flags.append(color)
        return True

    def GetFlagList(self) -> list[str]:
        return list(self._flags)

    def ClearFlags(self, color: Optional[str] = None) -> bool:
        if color is None:
            self._flags = []
        else:
            self._flags = [f for f in self._flags if f != color]
        return True

    def GetMetadata(self, key: Optional[str] = None) -> Any:
        return self._metadata if key is None else self._metadata.get(key, "")

    def SetMetadata(self, key: str, value: str) -> bool:
        self._metadata[key] = value
        return True


class FakeFolder:
    def __init__(self, name: str) -> None:
        self._name = name
        self._clips: list[FakeMediaPoolItem] = []
        self._subs: list["FakeFolder"] = []

    def GetName(self) -> str:
        return self._name

    def GetClipList(self) -> list[FakeMediaPoolItem]:
        return list(self._clips)

    def GetSubFolderList(self) -> list["FakeFolder"]:
        return list(self._subs)


class FakeMediaPool:
    def __init__(self) -> None:
        self._root = FakeFolder("Master")
        self._current = self._root

    def GetRootFolder(self) -> FakeFolder:
        return self._root

    def GetCurrentFolder(self) -> FakeFolder:
        return self._current

    def SetCurrentFolder(self, folder: FakeFolder) -> bool:
        self._current = folder
        return True

    def AddSubFolder(self, parent: FakeFolder, name: str) -> Optional[FakeFolder]:
        sub = FakeFolder(name)
        parent._subs.append(sub)
        return sub

    def ImportMedia(self, paths: list[str]) -> list[FakeMediaPoolItem]:
        # `os.path.basename` honors the host OS separator (Win = `\`, POSIX = `/`).
        items = [
            FakeMediaPoolItem(os.path.basename(p) or p, {"File Path": p})
            for p in paths
        ]
        self._current._clips.extend(items)
        return items

    def DeleteTimelines(self, timelines: list) -> bool:
        owner = getattr(self, "_owner", None)
        if owner is None:
            return False
        removed = False
        for tl in timelines:
            if tl in owner._timelines:
                owner._timelines.remove(tl)
                if owner._current_timeline is tl:
                    owner._current_timeline = (
                        owner._timelines[-1] if owner._timelines else None
                    )
                removed = True
        return removed

    def CreateEmptyTimeline(self, name: str) -> "FakeTimeline":  # forward-ref ok
        fps = 24.0
        owner = getattr(self, "_owner", None)
        if owner is not None:
            try:
                fps = float(owner._settings.get("timelineFrameRate", 24.0))
            except (TypeError, ValueError):
                fps = 24.0
        tl = FakeTimeline(name, fps=fps)
        if owner is not None:
            owner._timelines.append(tl)  # type: ignore[attr-defined]
            owner._current_timeline = tl  # type: ignore[attr-defined]
        return tl


class FakeTimelineItem:
    def __init__(self, name: str, start: int, end: int, source: Optional[FakeMediaPoolItem] = None) -> None:
        self._name = name
        self._start = start
        self._end = end
        self._source = source

    def GetName(self) -> str:
        return self._name

    def GetStart(self) -> int:
        return self._start

    def GetEnd(self) -> int:
        return self._end

    def GetDuration(self) -> int:
        return self._end - self._start

    def GetMediaPoolItem(self) -> Optional[FakeMediaPoolItem]:
        return self._source


class FakeTimeline:
    def __init__(self, name: str, fps: float = 24.0) -> None:
        self._name = name
        self._fps = fps
        self._markers: dict[int, dict[str, Any]] = {}
        # tracks: { "video": {1: [items]}, "audio": {1: []}, "subtitle": {1: []} }
        self._tracks: dict[str, dict[int, list[FakeTimelineItem]]] = {
            "video": {1: []},
            "audio": {1: []},
            "subtitle": {},
        }

    def GetName(self) -> str:
        return self._name

    def GetSetting(self, key: str) -> str:
        if key == "timelineFrameRate":
            return str(self._fps)
        return ""

    def SetSetting(self, key: str, value: str) -> bool:
        if key == "timelineFrameRate":
            try:
                self._fps = float(value)
            except (TypeError, ValueError):
                return False
        return True

    def GetTrackCount(self, track_type: str) -> int:
        return len(self._tracks.get(track_type, {}))

    def GetItemListInTrack(self, track_type: str, index: int) -> list[FakeTimelineItem]:
        return list(self._tracks.get(track_type, {}).get(index, []))

    def AddMarker(self, frame: int, color: str, name: str, note: str, duration: int) -> bool:
        if frame in self._markers:
            return False
        self._markers[int(frame)] = {
            "color": color, "name": name, "note": note, "duration": duration,
        }
        return True

    def GetMarkers(self) -> dict[int, dict[str, Any]]:
        return {k: dict(v) for k, v in self._markers.items()}

    def DeleteMarkerAtFrame(self, frame: int) -> bool:
        return self._markers.pop(int(frame), None) is not None

    # test helpers
    def _add_track_item(self, track_type: str, index: int, item: FakeTimelineItem) -> None:
        self._tracks.setdefault(track_type, {}).setdefault(index, []).append(item)


class FakeProject:
    def __init__(self, name: str) -> None:
        self._name = name
        self._media_pool = FakeMediaPool()
        self._media_pool._owner = self  # back-ref so CreateEmptyTimeline can register
        self._timelines: list[FakeTimeline] = []
        self._current_timeline: Optional[FakeTimeline] = None
        self._settings = {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        # render
        self._render_presets = ["H.264 Master", "ProRes 422 HQ"]
        self._render_jobs: list[dict[str, Any]] = []
        self._render_settings: dict[str, Any] = {}
        self._rendering = False

    def GetName(self) -> str:
        return self._name

    def GetSetting(self, key: str) -> str:
        return self._settings.get(key, "")

    def SetSetting(self, key: str, value: str) -> bool:
        self._settings[key] = value
        return True

    def GetMediaPool(self) -> FakeMediaPool:
        return self._media_pool

    # --- timelines ---
    def GetTimelineCount(self) -> int:
        return len(self._timelines)

    def GetTimelineByIndex(self, index: int) -> Optional[FakeTimeline]:
        if 1 <= index <= len(self._timelines):
            return self._timelines[index - 1]
        return None

    def GetCurrentTimeline(self) -> Optional[FakeTimeline]:
        return self._current_timeline

    def SetCurrentTimeline(self, timeline: FakeTimeline) -> bool:
        if timeline in self._timelines:
            self._current_timeline = timeline
            return True
        return False

    # --- render ---
    def GetRenderPresetList(self) -> list[str]:
        return list(self._render_presets)

    def LoadRenderPreset(self, name: str) -> bool:
        return name in self._render_presets

    def SetRenderSettings(self, settings: dict[str, Any]) -> bool:
        self._render_settings.update(settings)
        return True

    def AddRenderJob(self) -> str:
        jid = f"job-{len(self._render_jobs) + 1}"
        self._render_jobs.append(
            {
                "JobId": jid,
                "JobStatus": "Ready",
                "CompletionPercentage": 0,
                **self._render_settings,
            }
        )
        return jid

    def GetRenderJobList(self) -> list[dict[str, Any]]:
        return [dict(j) for j in self._render_jobs]

    def GetRenderJobStatus(self, job_id: str) -> dict[str, Any]:
        for j in self._render_jobs:
            if j["JobId"] == job_id:
                return {
                    "JobStatus": j["JobStatus"],
                    "CompletionPercentage": j["CompletionPercentage"],
                }
        return {}

    def StartRendering(self, job_ids: Optional[list[str]] = None) -> bool:
        self._rendering = True
        targets = job_ids or [j["JobId"] for j in self._render_jobs]
        for j in self._render_jobs:
            if j["JobId"] in targets:
                j["JobStatus"] = "Rendering"
        return True

    def StopRendering(self) -> None:
        self._rendering = False
        for j in self._render_jobs:
            if j["JobStatus"] == "Rendering":
                j["JobStatus"] = "Cancelled"

    def DeleteRenderJob(self, job_id: str) -> bool:
        before = len(self._render_jobs)
        self._render_jobs = [j for j in self._render_jobs if j["JobId"] != job_id]
        return len(self._render_jobs) != before

    # test helper
    def _force_job_status(self, job_id: str, status: str, progress: int = 0) -> None:
        for j in self._render_jobs:
            if j["JobId"] == job_id:
                j["JobStatus"] = status
                j["CompletionPercentage"] = progress


class FakeProjectManager:
    def __init__(self) -> None:
        self._projects: dict[str, FakeProject] = {}
        self._current: Optional[FakeProject] = None

    def GetProjectsInCurrentFolder(self) -> dict[int, str]:
        return {i + 1: name for i, name in enumerate(self._projects.keys())}

    def CreateProject(self, name: str) -> Optional[FakeProject]:
        if name in self._projects:
            return None
        p = FakeProject(name)
        self._projects[name] = p
        self._current = p
        return p

    def LoadProject(self, name: str) -> Optional[FakeProject]:
        if name not in self._projects:
            return None
        self._current = self._projects[name]
        return self._current

    def CloseProject(self, project: FakeProject) -> bool:
        if self._current is project:
            self._current = None
            return True
        return False

    def GetCurrentProject(self) -> Optional[FakeProject]:
        return self._current

    def SaveProject(self) -> bool:
        return self._current is not None

    def ExportProject(self, project_name: str, path: str) -> bool:
        return project_name in self._projects

    def ImportProject(self, path: str) -> bool:
        # Strip directory (any platform separator) and extension.
        name = os.path.splitext(os.path.basename(path))[0] or path
        if name in self._projects:
            return False
        self._projects[name] = FakeProject(name)
        return True


class FakeResolve:
    def __init__(
        self,
        version: str = "18.6.4",
        product: str = "DaVinci Resolve Studio",
    ) -> None:
        self._version = version
        self._product = product
        self._pm = FakeProjectManager()

    def GetVersionString(self) -> str:
        return self._version

    def GetProductName(self) -> str:
        return self._product

    def GetProjectManager(self) -> FakeProjectManager:
        return self._pm


class FakeDvrScript:
    """Stand-in for the DaVinciResolveScript module."""

    def __init__(self, resolve: Optional[FakeResolve]) -> None:
        self._resolve = resolve

    def scriptapp(self, kind: str) -> Optional[FakeResolve]:
        if kind != "Resolve":
            return None
        return self._resolve


# ---------- ResolveClient adapter (wraps FakeResolve to satisfy the Protocol) ----------

class FakeResolveClient:
    def __init__(self, resolve: FakeResolve) -> None:
        self._resolve = resolve

    def raw(self):  # noqa: D401
        return self._resolve

    def version(self) -> str:
        return self._resolve.GetVersionString()

    def edition(self) -> str:
        product = (self._resolve.GetProductName() or "").lower()
        return "Studio" if "studio" in product else "Free"

    def project_manager(self):
        return self._resolve.GetProjectManager()

    def current_project(self):
        return self._resolve.GetProjectManager().GetCurrentProject()


@pytest.fixture
def fake_resolve() -> FakeResolve:
    return FakeResolve()


@pytest.fixture
def fake_dvr_script(fake_resolve: FakeResolve) -> FakeDvrScript:
    return FakeDvrScript(fake_resolve)


@pytest.fixture
def fake_client(fake_resolve: FakeResolve) -> FakeResolveClient:
    return FakeResolveClient(fake_resolve)

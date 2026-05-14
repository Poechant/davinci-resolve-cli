"""Tool registry: maps MCP tool names to the v0.1 pure-function handlers.

Each entry is `(name, description, inputSchema_dict, handler)`. The handler
takes a `ResolveClient` and a `params` dict, returns a JSON-serializable result.

Tools mirror the CLI surface 1:1 so anything an agent can do via `dvr <cmd>`
is also reachable via MCP. Names use dot-notation (`project.list`, `media.tag`)
which renders cleanly in mainstream MCP clients.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..commands import doctor as doctor_cmd
from ..commands import media as media_cmd
from ..commands import project as project_cmd
from ..commands import render as render_cmd
from ..commands import timeline as timeline_cmd
from ..resolve import ResolveClient

Handler = Callable[[ResolveClient, dict[str, Any]], Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    needs_resolve: bool = True


# ---------- input schema helpers ----------

EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


# ---------- handlers ----------

def _h_doctor(_client, _params):
    return doctor_cmd.build_report()


def _h_project_list(client, _params):
    return project_cmd.list_projects(client)


def _h_project_current(client, _params):
    return project_cmd.current_project(client)


def _h_project_open(client, params):
    return project_cmd.open_project(client, params["name"])


def _h_project_new(client, params):
    return project_cmd.new_project(client, params["name"])


def _h_media_import(client, params):
    return media_cmd.import_media(
        client,
        params["path"],
        bin_name=params.get("bin"),
        recursive=bool(params.get("recursive", False)),
    )


def _h_media_list(client, params):
    return media_cmd.list_media(client, bin_name=params.get("bin"))


def _h_media_tag(client, params):
    return media_cmd.tag_clips(client, list(params["clipIds"]), color=params.get("color", "Green"))


def _h_render_presets(client, _params):
    return render_cmd.list_presets(client)


def _h_render_submit(client, params):
    return render_cmd.submit_render(
        client,
        preset=params["preset"],
        timeline=params.get("timeline"),
        output=params["output"],
        start=bool(params.get("start", False)),
    )


def _h_render_status(client, params):
    return render_cmd.get_status(client, params["jobId"])


def _h_render_list(client, _params):
    return render_cmd.list_jobs(client)


def _h_render_wait(client, params):
    return render_cmd.wait_job(
        client,
        params["jobId"],
        interval=float(params.get("interval", 1.0)),
        timeout=params.get("timeout"),
    )


def _h_render_cancel(client, params):
    return render_cmd.cancel_job(client, params["jobId"])


def _h_timeline_list(client, _params):
    return timeline_cmd.list_timelines(client)


def _h_timeline_current(client, _params):
    return timeline_cmd.current_timeline(client)


def _h_timeline_clips(client, params):
    return timeline_cmd.list_clips_in_timeline(client, timeline_name=params.get("timeline"))


def _h_timeline_marker_add(client, params):
    return timeline_cmd.add_marker(
        client,
        at=params["at"],
        note=params.get("note", ""),
        name=params.get("name", ""),
        color=params.get("color", "Blue"),
        duration=int(params.get("duration", 1)),
        timeline_name=params.get("timeline"),
        dry_run=bool(params.get("dryRun", False)),
    )


def _h_timeline_marker_delete(client, params):
    return timeline_cmd.delete_marker(
        client,
        at=params["at"],
        timeline_name=params.get("timeline"),
        dry_run=bool(params.get("dryRun", False)),
    )


def _h_timeline_marker_list(client, params):
    return timeline_cmd.list_markers(client, timeline_name=params.get("timeline"))


# ---------- registry ----------

def build_registry() -> list[ToolSpec]:
    return [
        # environment
        ToolSpec(
            "doctor",
            "Diagnose the DaVinci Resolve bridge environment. Returns a structured report.",
            EMPTY_SCHEMA,
            _h_doctor,
            needs_resolve=False,
        ),
        # project
        ToolSpec(
            "project.list",
            "List projects in the current Resolve project folder.",
            EMPTY_SCHEMA,
            _h_project_list,
        ),
        ToolSpec(
            "project.current",
            "Return metadata for the currently open project (name, timeline count, framerate, resolution).",
            EMPTY_SCHEMA,
            _h_project_current,
        ),
        ToolSpec(
            "project.open",
            "Open a project by name.",
            _schema({"name": {"type": "string"}}, ["name"]),
            _h_project_open,
        ),
        ToolSpec(
            "project.new",
            "Create a new project.",
            _schema({"name": {"type": "string"}}, ["name"]),
            _h_project_new,
        ),
        # media
        ToolSpec(
            "media.import",
            "Import a media file or folder into the media pool. Optionally recursive, optionally targeted at a named bin.",
            _schema(
                {
                    "path": {"type": "string"},
                    "bin": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
                ["path"],
            ),
            _h_media_import,
        ),
        ToolSpec(
            "media.list",
            "List clips in the current (or named) bin.",
            _schema({"bin": {"type": "string"}}),
            _h_media_list,
        ),
        ToolSpec(
            "media.tag",
            "Add a colored flag to one or more clips. Partial failures are reported, never rolled back.",
            _schema(
                {
                    "clipIds": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "color": {
                        "type": "string",
                        "enum": sorted(media_cmd.VALID_FLAG_COLORS),
                    },
                },
                ["clipIds"],
            ),
            _h_media_tag,
        ),
        # render
        ToolSpec(
            "render.presets",
            "List render presets available in the current project.",
            EMPTY_SCHEMA,
            _h_render_presets,
        ),
        ToolSpec(
            "render.submit",
            "Queue a render job. Returns a jobId immediately (non-blocking). Set start=true to also begin rendering.",
            _schema(
                {
                    "preset": {"type": "string"},
                    "output": {"type": "string"},
                    "timeline": {"type": "string"},
                    "start": {"type": "boolean"},
                },
                ["preset", "output"],
            ),
            _h_render_submit,
        ),
        ToolSpec(
            "render.status",
            "Get the live status (queued / rendering / completed / failed / cancelled) of a render job.",
            _schema({"jobId": {"type": "string"}}, ["jobId"]),
            _h_render_status,
        ),
        ToolSpec(
            "render.list",
            "List all render jobs (local store ∪ Resolve queue).",
            EMPTY_SCHEMA,
            _h_render_list,
        ),
        ToolSpec(
            "render.wait",
            "Poll a render job until it reaches a terminal state. interval and timeout are in seconds.",
            _schema(
                {
                    "jobId": {"type": "string"},
                    "interval": {"type": "number", "minimum": 0.1},
                    "timeout": {"type": "number"},
                },
                ["jobId"],
            ),
            _h_render_wait,
        ),
        ToolSpec(
            "render.cancel",
            "Cancel a queued or running render job.",
            _schema({"jobId": {"type": "string"}}, ["jobId"]),
            _h_render_cancel,
        ),
        # timeline
        ToolSpec(
            "timeline.list",
            "List all timelines in the current project.",
            EMPTY_SCHEMA,
            _h_timeline_list,
        ),
        ToolSpec(
            "timeline.current",
            "Return the currently selected timeline's name and fps.",
            EMPTY_SCHEMA,
            _h_timeline_current,
        ),
        ToolSpec(
            "timeline.clips",
            "List clips on a timeline (current by default). Output includes track type, index, start/end timecodes, source clip ref.",
            _schema({"timeline": {"type": "string"}}),
            _h_timeline_clips,
        ),
        ToolSpec(
            "timeline.marker_add",
            "Add a marker at a timecode. Supports dryRun.",
            _schema(
                {
                    "at": {"type": "string", "description": "Timecode HH:MM:SS:FF"},
                    "note": {"type": "string"},
                    "name": {"type": "string"},
                    "color": {"type": "string", "enum": sorted(timeline_cmd.VALID_MARKER_COLORS)},
                    "duration": {"type": "integer", "minimum": 1},
                    "timeline": {"type": "string"},
                    "dryRun": {"type": "boolean"},
                },
                ["at"],
            ),
            _h_timeline_marker_add,
        ),
        ToolSpec(
            "timeline.marker_delete",
            "Delete a marker at a timecode. Supports dryRun.",
            _schema(
                {
                    "at": {"type": "string"},
                    "timeline": {"type": "string"},
                    "dryRun": {"type": "boolean"},
                },
                ["at"],
            ),
            _h_timeline_marker_delete,
        ),
        ToolSpec(
            "timeline.marker_list",
            "List markers on a timeline.",
            _schema({"timeline": {"type": "string"}}),
            _h_timeline_marker_list,
        ),
    ]


def names() -> list[str]:
    return [t.name for t in build_registry()]

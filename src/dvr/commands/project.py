"""`dvr project ...` — project library management.

Business logic lives in `_pure` helpers; the Typer layer is a thin IO wrapper.
Tests can call the helpers directly with a fake ResolveClient.
"""
from __future__ import annotations

from typing import Any, Optional

import typer

from ..errors import ApiCallFailed, NotFound, ValidationError
from ..output import emit, resolve_format
from ..resolve import ResolveClient
from . import _client as client_mod

app = typer.Typer(help="Project library management.")


# ---------- pure helpers (unit-testable) ----------

def list_projects(client: ResolveClient) -> list[dict[str, Any]]:
    pm = client.project_manager()
    raw = pm.GetProjectsInCurrentFolder() or {}
    # Resolve returns dict[int, name] sometimes, list[name] other times — normalize.
    if isinstance(raw, dict):
        items = sorted(raw.items())
        return [{"index": int(idx), "name": name} for idx, name in items]
    return [{"index": i + 1, "name": name} for i, name in enumerate(raw)]


def open_project(client: ResolveClient, name: str) -> dict[str, Any]:
    pm = client.project_manager()
    proj = pm.LoadProject(name)
    if proj is None:
        raise NotFound("Project", name)
    return {"ok": True, "name": name}


def new_project(client: ResolveClient, name: str) -> dict[str, Any]:
    if not name.strip():
        raise ValidationError("project name must not be empty")
    pm = client.project_manager()
    proj = pm.CreateProject(name)
    if proj is None:
        raise ValidationError(
            f"could not create project '{name}' — name may already be in use",
            hint="Use `dvr project list` to inspect existing projects.",
        )
    return {"ok": True, "name": name}


def close_project(client: ResolveClient) -> dict[str, Any]:
    pm = client.project_manager()
    current = pm.GetCurrentProject()
    if current is None:
        raise ValidationError("no project is currently open", hint="Open one with `dvr project open <name>`.")
    if not pm.CloseProject(current):
        raise ApiCallFailed("CloseProject")
    return {"ok": True}


def save_project(client: ResolveClient) -> dict[str, Any]:
    pm = client.project_manager()
    if pm.GetCurrentProject() is None:
        raise ValidationError("no project is currently open")
    if not pm.SaveProject():
        raise ApiCallFailed("SaveProject")
    return {"ok": True}


def export_project(client: ResolveClient, path: str) -> dict[str, Any]:
    pm = client.project_manager()
    current = pm.GetCurrentProject()
    if current is None:
        raise ValidationError("no project is currently open to export")
    name = current.GetName()
    if not pm.ExportProject(name, path):
        raise ApiCallFailed("ExportProject", path)
    return {"ok": True, "name": name, "path": path}


def import_project(client: ResolveClient, path: str) -> dict[str, Any]:
    pm = client.project_manager()
    if not pm.ImportProject(path):
        raise ApiCallFailed("ImportProject", path)
    return {"ok": True, "path": path}


def current_project(client: ResolveClient) -> dict[str, Any]:
    pm = client.project_manager()
    proj = pm.GetCurrentProject()
    if proj is None:
        raise ValidationError("no project is currently open")
    fps_str = proj.GetSetting("timelineFrameRate") or "24"
    width = proj.GetSetting("timelineResolutionWidth") or "1920"
    height = proj.GetSetting("timelineResolutionHeight") or "1080"
    return {
        "name": proj.GetName(),
        "timelineCount": int(proj.GetTimelineCount() or 0),
        "framerate": float(fps_str),
        "resolution": {"width": int(width), "height": int(height)},
    }


# ---------- typer wrappers ----------

def _emit(data: Any, fmt: Optional[str]) -> None:
    emit(data, resolve_format(fmt))


@app.command("list")
def cli_list(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """List projects in the current folder."""
    _emit(list_projects(client_mod.get()), fmt)


@app.command("open")
def cli_open(name: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Open a project by name."""
    _emit(open_project(client_mod.get(), name), fmt)


@app.command("new")
def cli_new(name: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Create a new project."""
    _emit(new_project(client_mod.get(), name), fmt)


@app.command("close")
def cli_close(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Close the currently open project."""
    _emit(close_project(client_mod.get()), fmt)


@app.command("save")
def cli_save(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Save the currently open project."""
    _emit(save_project(client_mod.get()), fmt)


@app.command("export")
def cli_export(path: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Export the current project to a .drp file."""
    _emit(export_project(client_mod.get(), path), fmt)


@app.command("import")
def cli_import(path: str, fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Import a project from a .drp file."""
    _emit(import_project(client_mod.get(), path), fmt)


@app.command("current")
def cli_current(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """Show metadata for the currently open project."""
    _emit(current_project(client_mod.get()), fmt)

"""`dvr media ...` — media pool batch operations."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import typer

from ..errors import ApiCallFailed, NotFound, ValidationError
from ..output import emit, resolve_format
from ..resolve import ResolveClient
from . import _client as client_mod

app = typer.Typer(help="Media pool batch operations.")

SUPPORTED_EXTS = {
    # video
    ".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mxf", ".braw", ".r3d",
    # audio
    ".wav", ".mp3", ".aac", ".aif", ".aiff", ".flac",
    # images
    ".jpg", ".jpeg", ".png", ".exr", ".dpx", ".tif", ".tiff",
}

# DaVinci Resolve only accepts these flag colors
VALID_FLAG_COLORS = {
    "Blue", "Cyan", "Green", "Yellow", "Red", "Pink",
    "Purple", "Fuchsia", "Rose", "Lavender", "Sky",
    "Mint", "Lemon", "Sand", "Cocoa", "Cream",
}


# ---------- helpers ----------

def _current_project_or_raise(client: ResolveClient):
    proj = client.project_manager().GetCurrentProject()
    if proj is None:
        raise ValidationError("no project is currently open")
    return proj


def _find_subfolder(parent, name: str):
    for sub in parent.GetSubFolderList() or []:
        if sub.GetName() == name:
            return sub
    return None


def _select_bin(media_pool, bin_name: Optional[str]):
    if bin_name is None:
        return media_pool.GetCurrentFolder()
    root = media_pool.GetRootFolder()
    if bin_name in ("/", "Master", "root"):
        return root
    folder = _find_subfolder(root, bin_name)
    if folder is None:
        raise NotFound("Bin", bin_name)
    return folder


def _expand_paths(path: str, recursive: bool) -> list[str]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    if p.is_file():
        return [str(p)]
    if not recursive:
        return [str(child) for child in sorted(p.iterdir()) if child.is_file() and child.suffix.lower() in SUPPORTED_EXTS]
    out: list[str] = []
    for root, _dirs, files in os.walk(p):
        for f in sorted(files):
            if Path(f).suffix.lower() in SUPPORTED_EXTS:
                out.append(str(Path(root) / f))
    return out


def _clip_to_dict(item) -> dict[str, Any]:
    return {
        "id": item.GetMediaId(),
        "name": item.GetName(),
        "resolution": item.GetClipProperty("Resolution") or None,
        "duration": item.GetClipProperty("Duration") or None,
        "codec": item.GetClipProperty("Format") or None,
        "fps": item.GetClipProperty("FPS") or None,
        "type": item.GetClipProperty("Type") or None,
        "flags": item.GetFlagList() if hasattr(item, "GetFlagList") else [],
    }


# ---------- pure helpers (unit-testable) ----------

def import_media(
    client: ResolveClient,
    path: str,
    *,
    bin_name: Optional[str] = None,
    recursive: bool = False,
) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    mp = proj.GetMediaPool()
    target = _select_bin(mp, bin_name)
    previous = mp.GetCurrentFolder()
    mp.SetCurrentFolder(target)

    candidates = _expand_paths(path, recursive)
    if not candidates:
        if not Path(path).expanduser().exists():
            raise ValidationError(f"path does not exist: {path}")
        raise ValidationError(
            f"no supported media under {path}",
            hint=f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTS))}",
        )
    imported: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    try:
        for candidate in candidates:
            try:
                result = mp.ImportMedia([candidate]) or []
                if not result:
                    failed.append({"path": candidate, "reason": "Resolve refused the file"})
                    continue
                for item in result:
                    imported.append(
                        {"id": item.GetMediaId(), "name": item.GetName(), "path": candidate}
                    )
            except Exception as exc:  # noqa: BLE001
                failed.append({"path": candidate, "reason": str(exc)})
    finally:
        # `import` is a one-shot op; do not leave Resolve's current bin pointing somewhere new.
        mp.SetCurrentFolder(previous)
    return {"imported": imported, "failed": failed}


def list_media(
    client: ResolveClient,
    *,
    bin_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    proj = _current_project_or_raise(client)
    mp = proj.GetMediaPool()
    target = _select_bin(mp, bin_name)
    return [_clip_to_dict(item) for item in (target.GetClipList() or [])]


def tag_clips(
    client: ResolveClient,
    clip_ids: list[str],
    *,
    color: str,
) -> dict[str, Any]:
    if not clip_ids:
        raise ValidationError("at least one clipId is required")
    if color not in VALID_FLAG_COLORS:
        raise ValidationError(
            f"invalid flag color: {color}",
            hint=f"Valid colors: {', '.join(sorted(VALID_FLAG_COLORS))}",
        )
    proj = _current_project_or_raise(client)
    mp = proj.GetMediaPool()

    # Index all clips by id across all folders
    by_id: dict[str, Any] = {}

    def _walk(folder) -> None:
        for clip in folder.GetClipList() or []:
            by_id[clip.GetMediaId()] = clip
        for sub in folder.GetSubFolderList() or []:
            _walk(sub)

    _walk(mp.GetRootFolder())

    tagged: list[str] = []
    failed: list[dict[str, str]] = []
    for cid in clip_ids:
        clip = by_id.get(cid)
        if clip is None:
            failed.append({"clipId": cid, "reason": "not found"})
            continue
        try:
            if not clip.AddFlag(color):
                failed.append({"clipId": cid, "reason": "AddFlag returned false"})
            else:
                tagged.append(cid)
        except Exception as exc:  # noqa: BLE001
            failed.append({"clipId": cid, "reason": str(exc)})
    return {"tagged": tagged, "failed": failed}


# ---------- typer wrappers ----------

@app.command("import")
def cli_import(
    path: str,
    bin: Optional[str] = typer.Option(None, "--bin", "-b", help="Target bin name."),
    recursive: bool = typer.Option(False, "--recursive", "-r"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Import media files (or a folder) into the media pool."""
    result = import_media(client_mod.get(), path, bin_name=bin, recursive=recursive)
    emit(result, resolve_format(fmt))


@app.command("list")
def cli_list(
    bin: Optional[str] = typer.Option(None, "--bin", "-b"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """List clips in the current (or named) bin."""
    emit(list_media(client_mod.get(), bin_name=bin), resolve_format(fmt))


@app.command("tag")
def cli_tag(
    clip_ids: list[str] = typer.Argument(..., help="One or more clip IDs."),
    color: str = typer.Option("Green", "--color", "-c", help="Flag color."),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Add a colored flag to one or more clips."""
    emit(tag_clips(client_mod.get(), clip_ids, color=color), resolve_format(fmt))

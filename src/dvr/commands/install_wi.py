"""`dvr install-wi` — deploy the Workflow Integration plugin to the local Resolve install."""
from __future__ import annotations

import platform
import shutil
from pathlib import Path
from typing import Optional

import typer

from ..errors import ValidationError
from ..output import emit, resolve_format

app = typer.Typer(help="Install / uninstall the DVR CLI Bridge Workflow Integration plugin.")

PLUGIN_FILES = ["manifest.xml", "index.html", "server.js"]
PLUGIN_FOLDER_NAME = "dvr-cli-bridge"


def plugin_dest_dir(platform_name: Optional[str] = None) -> Path:
    """Where Resolve looks for Workflow Integration plugins on the current OS."""
    sysname = (platform_name or platform.system()).lower()
    if sysname == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Blackmagic Design"
            / "DaVinci Resolve"
            / "Fusion"
            / "Workflow Integration Plugins"
            / PLUGIN_FOLDER_NAME
        )
    if sysname == "windows":
        # %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Workflow Integration Plugins\
        import os
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return (
            Path(appdata)
            / "Blackmagic Design"
            / "DaVinci Resolve"
            / "Support"
            / "Fusion"
            / "Workflow Integration Plugins"
            / PLUGIN_FOLDER_NAME
        )
    if sysname == "linux":
        return (
            Path.home()
            / ".local"
            / "share"
            / "DaVinciResolve"
            / "Fusion"
            / "Workflow Integration Plugins"
            / PLUGIN_FOLDER_NAME
        )
    raise ValidationError(f"unsupported platform for WI install: {sysname}")


def plugin_source_dir() -> Path:
    """Bundled wi-plugin/ folder (sibling of the dvr package in the wheel)."""
    # In an editable / source install: <repo>/wi-plugin/
    # In an installed wheel: same directory under share/dvr/ via pyproject shared-data
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent.parent / "wi-plugin",   # source repo
        here.parent.parent / "wi-plugin",                 # installed alongside package (if shipped that way)
    ]
    for c in candidates:
        if all((c / f).exists() for f in PLUGIN_FILES):
            return c
    raise ValidationError(
        "wi-plugin/ source not found",
        hint="If installing from a wheel, reinstall with the wi-plugin extras enabled.",
    )


def install(*, force: bool = False, source_dir: Optional[Path] = None, dest_dir: Optional[Path] = None) -> dict:
    src = source_dir or plugin_source_dir()
    dst = dest_dir or plugin_dest_dir()
    dst.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    for name in PLUGIN_FILES:
        src_file = src / name
        dst_file = dst / name
        if dst_file.exists() and not force:
            if dst_file.read_bytes() == src_file.read_bytes():
                actions.append(f"unchanged: {name}")
                continue
        shutil.copy2(src_file, dst_file)
        actions.append(f"copied: {name}")
    return {"ok": True, "dest": str(dst), "actions": actions}


def uninstall(*, dest_dir: Optional[Path] = None) -> dict:
    dst = dest_dir or plugin_dest_dir()
    if not dst.exists():
        return {"ok": True, "dest": str(dst), "removed": False}
    shutil.rmtree(dst)
    return {"ok": True, "dest": str(dst), "removed": True}


@app.callback(invoke_without_command=True)
def cli_install_wi(
    uninstall_flag: bool = typer.Option(False, "--uninstall", "-u", help="Remove the plugin instead of installing."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files even if unchanged."),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Install (or --uninstall) the Workflow Integration plugin."""
    result = uninstall() if uninstall_flag else install(force=force)
    emit(result, resolve_format(fmt))

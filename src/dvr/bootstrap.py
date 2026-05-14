"""Locate and load DaVinciResolveScript, then connect to the running Resolve instance.

Platform-specific defaults follow Blackmagic's published Scripting README (Resolve 18+):

  macOS:
    RESOLVE_SCRIPT_API = /Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting
    RESOLVE_SCRIPT_LIB = /Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so

  Windows:
    RESOLVE_SCRIPT_API = %PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting
    RESOLVE_SCRIPT_LIB = C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll

  Linux:
    RESOLVE_SCRIPT_API = /opt/resolve/Developer/Scripting
    RESOLVE_SCRIPT_LIB = /opt/resolve/libs/Fusion/fusionscript.so
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .errors import ApiUnavailable, ResolveNotRunning, VersionUnsupported

MIN_RESOLVE_MAJOR = 18


@dataclass
class BridgePaths:
    api_dir: Optional[Path]
    lib_path: Optional[Path]
    module_path: Optional[Path]
    platform: str


def default_paths(platform_name: Optional[str] = None) -> tuple[Optional[Path], Optional[Path]]:
    sysname = (platform_name or platform.system()).lower()
    if sysname == "darwin":
        api = Path(
            "/Library/Application Support/Blackmagic Design/"
            "DaVinci Resolve/Developer/Scripting"
        )
        lib = Path(
            "/Applications/DaVinci Resolve/DaVinci Resolve.app/"
            "Contents/Libraries/Fusion/fusionscript.so"
        )
        return api, lib
    if sysname == "windows":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        api = Path(program_data) / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Developer" / "Scripting"
        lib = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
        return api, lib
    if sysname == "linux":
        return Path("/opt/resolve/Developer/Scripting"), Path("/opt/resolve/libs/Fusion/fusionscript.so")
    return None, None


def discover_paths(env: Optional[dict[str, str]] = None) -> BridgePaths:
    """Resolve API/LIB paths from env vars first, then platform defaults."""
    env = env if env is not None else os.environ
    api_env = env.get("RESOLVE_SCRIPT_API")
    lib_env = env.get("RESOLVE_SCRIPT_LIB")

    api_default, lib_default = default_paths()
    api_dir = Path(api_env) if api_env else api_default
    lib_path = Path(lib_env) if lib_env else lib_default

    module_path: Optional[Path] = None
    if api_dir is not None:
        candidate = api_dir / "Modules" / "DaVinciResolveScript.py"
        if candidate.exists():
            module_path = candidate

    return BridgePaths(
        api_dir=api_dir,
        lib_path=lib_path,
        module_path=module_path,
        platform=platform.system(),
    )


def inject_sys_path(paths: BridgePaths) -> None:
    if paths.api_dir is not None:
        modules_dir = str(paths.api_dir / "Modules")
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
    if paths.api_dir is not None:
        os.environ.setdefault("RESOLVE_SCRIPT_API", str(paths.api_dir))
    if paths.lib_path is not None:
        os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(paths.lib_path))


def _import_dvr_script() -> Any:
    try:
        import DaVinciResolveScript as dvr_script  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ApiUnavailable(f"cannot import DaVinciResolveScript ({exc})") from exc
    return dvr_script


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse '18.6.4' or '18.5' or '18.6b1' into a tuple of ints.

    Each dot-separated chunk contributes its leading digit prefix; non-digit
    suffixes (build tags like 'b1') are discarded. Stops at the first chunk
    that has no leading digit.
    """
    parts: list[int] = []
    for chunk in version_str.split("."):
        prefix = ""
        for c in chunk:
            if c.isdigit():
                prefix += c
            else:
                break
        if not prefix:
            break
        parts.append(int(prefix))
    return tuple(parts)


def connect_resolve(paths: Optional[BridgePaths] = None) -> Any:
    """Returns a live Resolve handle, or raises a DvrError.

    Side-effects: mutates sys.path and os.environ so DaVinciResolveScript can find fusionscript.
    """
    paths = paths or discover_paths()
    if paths.module_path is None:
        raise ApiUnavailable(
            f"DaVinciResolveScript module not found under "
            f"{paths.api_dir}/Modules. Set RESOLVE_SCRIPT_API if installed elsewhere."
        )
    if paths.lib_path is None or not paths.lib_path.exists():
        raise ApiUnavailable(
            f"fusionscript library not found at {paths.lib_path}. "
            f"Set RESOLVE_SCRIPT_LIB if installed elsewhere."
        )

    inject_sys_path(paths)
    dvr_script = _import_dvr_script()
    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise ResolveNotRunning()

    try:
        version_str = resolve.GetVersionString()
    except Exception as exc:  # noqa: BLE001 — DVR throws bare exceptions
        raise ApiUnavailable(f"GetVersionString failed: {exc}") from exc

    version_tuple = parse_version(version_str or "")
    if not version_tuple or version_tuple[0] < MIN_RESOLVE_MAJOR:
        raise VersionUnsupported(version_str or "unknown")

    return resolve

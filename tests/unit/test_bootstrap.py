"""AC1 fragment + AC3 — bootstrap discovery and connection."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dvr import bootstrap
from dvr.errors import ApiUnavailable, ResolveNotRunning, VersionUnsupported


def test_default_paths_macos() -> None:
    api, lib = bootstrap.default_paths("Darwin")
    assert api is not None and "Blackmagic Design" in str(api)
    assert lib is not None and lib.suffix == ".so"


def test_default_paths_windows() -> None:
    api, lib = bootstrap.default_paths("Windows")
    assert api is not None and "Blackmagic Design" in str(api)
    assert lib is not None and str(lib).endswith(".dll")


def test_default_paths_linux() -> None:
    api, lib = bootstrap.default_paths("Linux")
    assert api == Path("/opt/resolve/Developer/Scripting")
    assert lib == Path("/opt/resolve/libs/Fusion/fusionscript.so")


def test_default_paths_unknown_platform_returns_none() -> None:
    api, lib = bootstrap.default_paths("Plan9")
    assert api is None and lib is None


def test_discover_paths_respects_env_overrides() -> None:
    paths = bootstrap.discover_paths(env={"RESOLVE_SCRIPT_API": "/tmp/api", "RESOLVE_SCRIPT_LIB": "/tmp/lib.so"})
    assert paths.api_dir == Path("/tmp/api")
    assert paths.lib_path == Path("/tmp/lib.so")


def test_discover_paths_finds_module_when_present(tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = bootstrap.discover_paths(env={"RESOLVE_SCRIPT_API": str(tmp_path), "RESOLVE_SCRIPT_LIB": str(lib)})
    assert paths.module_path == modules / "DaVinciResolveScript.py"


@pytest.mark.parametrize(
    "v,expected",
    [
        ("18.6.4", (18, 6, 4)),
        ("18.5", (18, 5)),
        ("18", (18,)),
        ("18.6b1", (18, 6)),
        ("", ()),
    ],
)
def test_parse_version(v: str, expected: tuple) -> None:
    assert bootstrap.parse_version(v) == expected


def test_connect_resolve_raises_when_module_missing(tmp_path: Path) -> None:
    paths = bootstrap.BridgePaths(
        api_dir=tmp_path,
        lib_path=tmp_path / "missing.so",
        module_path=None,
        platform="Darwin",
    )
    with pytest.raises(ApiUnavailable):
        bootstrap.connect_resolve(paths)


def test_connect_resolve_raises_when_lib_missing(tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    paths = bootstrap.BridgePaths(
        api_dir=tmp_path,
        lib_path=tmp_path / "missing.so",
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )
    with pytest.raises(ApiUnavailable):
        bootstrap.connect_resolve(paths)


def test_connect_resolve_raises_when_resolve_returns_none(monkeypatch, tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = bootstrap.BridgePaths(
        api_dir=tmp_path,
        lib_path=lib,
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )

    class _Mod:
        @staticmethod
        def scriptapp(_kind: str):
            return None

    monkeypatch.setattr(bootstrap, "_import_dvr_script", lambda: _Mod)
    with pytest.raises(ResolveNotRunning):
        bootstrap.connect_resolve(paths)


def test_connect_resolve_rejects_old_version(monkeypatch, tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = bootstrap.BridgePaths(
        api_dir=tmp_path,
        lib_path=lib,
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )

    class _FakeResolve:
        def GetVersionString(self) -> str:
            return "17.4"

        def GetProductName(self) -> str:
            return "DaVinci Resolve"

    class _Mod:
        @staticmethod
        def scriptapp(_kind: str):
            return _FakeResolve()

    monkeypatch.setattr(bootstrap, "_import_dvr_script", lambda: _Mod)
    with pytest.raises(VersionUnsupported):
        bootstrap.connect_resolve(paths)

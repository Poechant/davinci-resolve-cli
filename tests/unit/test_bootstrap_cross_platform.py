"""V2 AC5/AC6 — cross-platform path discovery + doctor report.

These tests run on the host OS but exercise the discovery logic for the
*other* OSes by passing the platform name explicitly. The real `connect_resolve`
is not exercised — that requires a running Resolve.
"""
from __future__ import annotations

from pathlib import PureWindowsPath, PurePosixPath

import pytest

from dvr import bootstrap
from dvr.commands.doctor import build_report


def _norm(p) -> str:
    """Normalize path separators so asserts work no matter the host OS.

    `Path("/opt/resolve")` on a Windows host becomes `WindowsPath('/opt/resolve')`
    whose `str()` is `\\opt\\resolve` — we coerce both forms to forward slashes
    before comparing.
    """
    return str(p).replace("\\", "/")


@pytest.mark.parametrize(
    "platform_name,expect_substring,lib_suffix",
    [
        ("Darwin", "Blackmagic Design", ".so"),
        ("Windows", "Blackmagic Design", ".dll"),
        ("Linux", "/opt/resolve", ".so"),
    ],
)
def test_default_paths_per_platform(platform_name: str, expect_substring: str, lib_suffix: str) -> None:
    api, lib = bootstrap.default_paths(platform_name)
    assert api is not None and expect_substring in _norm(api)
    assert lib is not None and _norm(lib).endswith(lib_suffix)


def test_windows_path_contains_program_files(monkeypatch) -> None:
    """Even when PROGRAMDATA is unset, default falls back to C:\\ProgramData."""
    monkeypatch.delenv("PROGRAMDATA", raising=False)
    api, lib = bootstrap.default_paths("Windows")
    assert api is not None and ("ProgramData" in _norm(api) or "PROGRAMDATA" in _norm(api))
    assert lib is not None and "Program Files" in _norm(lib)


def test_windows_program_data_env_override(monkeypatch) -> None:
    monkeypatch.setenv("PROGRAMDATA", r"D:\Shared\PD")
    api, _ = bootstrap.default_paths("Windows")
    assert api is not None and "D:" in _norm(api)


def test_linux_paths_are_posix() -> None:
    api, lib = bootstrap.default_paths("Linux")
    assert _norm(api).startswith("/opt/resolve")
    assert _norm(lib).startswith("/opt/resolve")


def test_unknown_platform_returns_none() -> None:
    api, lib = bootstrap.default_paths("Haiku")
    assert api is None and lib is None


def test_discover_paths_env_overrides_on_any_platform(tmp_path) -> None:
    paths = bootstrap.discover_paths(env={
        "RESOLVE_SCRIPT_API": str(tmp_path / "api"),
        "RESOLVE_SCRIPT_LIB": str(tmp_path / "lib.so"),
    })
    assert str(paths.api_dir).endswith("api")
    assert str(paths.lib_path).endswith("lib.so")


def test_doctor_report_when_resolve_absent(tmp_path) -> None:
    """On CI runners with no Resolve install, doctor still produces a structured report."""
    paths = bootstrap.BridgePaths(
        api_dir=tmp_path / "absent",
        lib_path=tmp_path / "absent.so",
        module_path=None,
        platform="Linux",
    )
    report = build_report(paths=paths)
    assert report["bridgeStatus"] == "module_not_found"
    assert report["resolveRunning"] is False
    assert len(report["issues"]) >= 1
    # platform field should be populated regardless of OS
    assert isinstance(report["platform"], str) and len(report["platform"]) > 0

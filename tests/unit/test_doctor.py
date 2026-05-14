"""AC2 — `dvr doctor` produces a schema-valid report covering Resolve state."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.bootstrap import BridgePaths
from dvr.commands.doctor import build_report

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "doctor.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_report_schema_valid_when_module_missing(tmp_path: Path) -> None:
    paths = BridgePaths(
        api_dir=tmp_path,
        lib_path=tmp_path / "missing.so",
        module_path=None,
        platform="Darwin",
    )
    report = build_report(paths=paths)
    jsonschema.validate(report, _schema())
    assert report["resolveRunning"] is False
    assert report["bridgeStatus"] == "module_not_found"
    assert any(i["code"] == "module_not_found" for i in report["issues"])
    assert all("hint" in i for i in report["issues"])


def test_report_when_resolve_running(tmp_path: Path, fake_dvr_script) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = BridgePaths(
        api_dir=tmp_path,
        lib_path=lib,
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )
    report = build_report(paths=paths, importer=lambda: fake_dvr_script)
    jsonschema.validate(report, _schema())
    assert report["resolveRunning"] is True
    assert report["bridgeStatus"] == "ok"
    assert report["version"].startswith("18")
    assert report["edition"] in {"Studio", "Free"}
    assert report["issues"] == []


def test_report_when_resolve_not_running(tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = BridgePaths(
        api_dir=tmp_path,
        lib_path=lib,
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )

    class _Mod:
        @staticmethod
        def scriptapp(_kind: str):
            return None

    report = build_report(paths=paths, importer=lambda: _Mod)
    jsonschema.validate(report, _schema())
    assert report["resolveRunning"] is False
    assert report["bridgeStatus"] == "connect_failed"


def test_report_when_version_too_old(tmp_path: Path) -> None:
    modules = tmp_path / "Modules"
    modules.mkdir()
    (modules / "DaVinciResolveScript.py").write_text("# stub")
    lib = tmp_path / "fusionscript.so"
    lib.write_text("")
    paths = BridgePaths(
        api_dir=tmp_path,
        lib_path=lib,
        module_path=modules / "DaVinciResolveScript.py",
        platform="Darwin",
    )

    class _R:
        def GetVersionString(self):
            return "17.4"

        def GetProductName(self):
            return "DaVinci Resolve"

    class _Mod:
        @staticmethod
        def scriptapp(_kind: str):
            return _R()

    report = build_report(paths=paths, importer=lambda: _Mod)
    jsonschema.validate(report, _schema())
    assert report["bridgeStatus"] == "version_unsupported"
    assert any(i["code"] == "version_unsupported" for i in report["issues"])

"""AC4 / AC5 — `dvr project ...` business logic."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.commands import project as proj
from dvr.errors import ApiCallFailed, NotFound, ValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "project.json"


def _schemas() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


# ---------- list ----------

def test_list_projects_empty(fake_client) -> None:
    assert proj.list_projects(fake_client) == []


def test_list_projects_after_create(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    proj.new_project(fake_client, "alt")
    items = proj.list_projects(fake_client)
    assert {i["name"] for i in items} == {"demo", "alt"}
    jsonschema.validate(items, _schemas()["$defs"]["ProjectList"])


# ---------- new ----------

def test_new_project_creates(fake_client) -> None:
    out = proj.new_project(fake_client, "demo")
    assert out == {"ok": True, "name": "demo"}


def test_new_project_duplicate_raises(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    with pytest.raises(ValidationError):
        proj.new_project(fake_client, "demo")


def test_new_project_empty_name_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        proj.new_project(fake_client, "   ")


# ---------- open ----------

def test_open_existing_project(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    out = proj.open_project(fake_client, "demo")
    assert out == {"ok": True, "name": "demo"}


def test_open_missing_project_raises(fake_client) -> None:
    with pytest.raises(NotFound):
        proj.open_project(fake_client, "ghost")


# ---------- close ----------

def test_close_with_no_project_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        proj.close_project(fake_client)


def test_close_after_create(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    out = proj.close_project(fake_client)
    assert out == {"ok": True}


# ---------- save ----------

def test_save_without_open_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        proj.save_project(fake_client)


def test_save_succeeds(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    assert proj.save_project(fake_client) == {"ok": True}


# ---------- export ----------

def test_export_without_open_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        proj.export_project(fake_client, "/tmp/x.drp")


def test_export_succeeds(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    out = proj.export_project(fake_client, "/tmp/x.drp")
    assert out == {"ok": True, "name": "demo", "path": "/tmp/x.drp"}


# ---------- import ----------

def test_import_creates_new_project(fake_client) -> None:
    out = proj.import_project(fake_client, "/path/to/fresh.drp")
    assert out == {"ok": True, "path": "/path/to/fresh.drp"}
    assert any(p["name"] == "fresh" for p in proj.list_projects(fake_client))


def test_import_duplicate_raises(fake_client) -> None:
    proj.new_project(fake_client, "fresh")
    with pytest.raises(ApiCallFailed):
        proj.import_project(fake_client, "/x/fresh.drp")


# ---------- current ----------

def test_current_without_open_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        proj.current_project(fake_client)


def test_current_returns_metadata(fake_client) -> None:
    proj.new_project(fake_client, "demo")
    out = proj.current_project(fake_client)
    assert out["name"] == "demo"
    assert out["timelineCount"] == 0
    assert out["framerate"] == 24.0
    assert out["resolution"] == {"width": 1920, "height": 1080}
    jsonschema.validate(out, _schemas()["$defs"]["ProjectCurrent"])

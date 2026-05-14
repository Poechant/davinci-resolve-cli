"""AC6 / AC7 / AC8 — media import / list / tag."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.commands import media
from dvr.commands import project as proj
from dvr.errors import NotFound, ValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "media.json"


def _schemas() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture
def ready_client(fake_client):
    """A client with one open project; ready for media ops."""
    proj.new_project(fake_client, "demo")
    return fake_client


# ---------- import ----------

def test_import_file(tmp_path, ready_client) -> None:
    f = tmp_path / "shot.mov"
    f.write_bytes(b"x")
    out = media.import_media(ready_client, str(f))
    assert len(out["imported"]) == 1
    assert out["imported"][0]["name"] == "shot.mov"
    assert out["failed"] == []
    jsonschema.validate(out, _schemas()["$defs"]["ImportResult"])


def test_import_dir_recursive(tmp_path, ready_client) -> None:
    (tmp_path / "a.mov").write_bytes(b"x")
    sub = tmp_path / "day2"
    sub.mkdir()
    (sub / "b.mp4").write_bytes(b"x")
    (tmp_path / "ignore.txt").write_text("not media")
    out = media.import_media(ready_client, str(tmp_path), recursive=True)
    names = {row["name"] for row in out["imported"]}
    assert names == {"a.mov", "b.mp4"}


def test_import_dir_non_recursive_skips_subdirs(tmp_path, ready_client) -> None:
    (tmp_path / "top.mov").write_bytes(b"x")
    sub = tmp_path / "deep"
    sub.mkdir()
    (sub / "hidden.mov").write_bytes(b"x")
    out = media.import_media(ready_client, str(tmp_path), recursive=False)
    names = {row["name"] for row in out["imported"]}
    assert names == {"top.mov"}


def test_import_missing_path_raises(ready_client) -> None:
    with pytest.raises(ValidationError):
        media.import_media(ready_client, "/nope/missing.mov")


def test_import_unsupported_only_raises(tmp_path, ready_client) -> None:
    (tmp_path / "doc.txt").write_text("hello")
    with pytest.raises(ValidationError):
        media.import_media(ready_client, str(tmp_path), recursive=True)


def test_import_with_bin_uses_subfolder(tmp_path, ready_client, fake_resolve) -> None:
    # Pre-create a sub-bin in the fake project
    proj_handle = fake_resolve.GetProjectManager().GetCurrentProject()
    mp = proj_handle.GetMediaPool()
    mp.AddSubFolder(mp.GetRootFolder(), "Day1")
    f = tmp_path / "x.mov"
    f.write_bytes(b"x")
    media.import_media(ready_client, str(f), bin_name="Day1")
    # Verify clip ended up in Day1
    day1 = [b for b in mp.GetRootFolder().GetSubFolderList() if b.GetName() == "Day1"][0]
    assert len(day1.GetClipList()) == 1


def test_import_to_missing_bin_raises(tmp_path, ready_client) -> None:
    f = tmp_path / "x.mov"
    f.write_bytes(b"x")
    with pytest.raises(NotFound):
        media.import_media(ready_client, str(f), bin_name="ghost")


def test_import_without_project_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        media.import_media(fake_client, "/x")


# ---------- list ----------

def test_list_empty(ready_client) -> None:
    assert media.list_media(ready_client) == []


def test_list_returns_clip_fields(tmp_path, ready_client) -> None:
    (tmp_path / "shot.mov").write_bytes(b"x")
    media.import_media(ready_client, str(tmp_path / "shot.mov"))
    out = media.list_media(ready_client)
    assert len(out) == 1
    row = out[0]
    assert set(row.keys()) >= {"id", "name", "resolution", "duration", "codec", "fps", "type", "flags"}
    jsonschema.validate(out, _schemas()["$defs"]["ClipList"])


def test_list_filters_by_bin(tmp_path, ready_client, fake_resolve) -> None:
    proj_handle = fake_resolve.GetProjectManager().GetCurrentProject()
    mp = proj_handle.GetMediaPool()
    mp.AddSubFolder(mp.GetRootFolder(), "Day1")
    f = tmp_path / "x.mov"
    f.write_bytes(b"x")
    media.import_media(ready_client, str(f), bin_name="Day1")
    assert media.list_media(ready_client, bin_name="Day1") != []
    assert media.list_media(ready_client) == []  # root is empty


# ---------- tag ----------

def test_tag_single_clip(tmp_path, ready_client) -> None:
    (tmp_path / "x.mov").write_bytes(b"x")
    media.import_media(ready_client, str(tmp_path / "x.mov"))
    cid = media.list_media(ready_client)[0]["id"]
    out = media.tag_clips(ready_client, [cid], color="Green")
    assert out == {"tagged": [cid], "failed": []}
    jsonschema.validate(out, _schemas()["$defs"]["TagResult"])


def test_tag_partial_failure_no_rollback(tmp_path, ready_client) -> None:
    (tmp_path / "x.mov").write_bytes(b"x")
    media.import_media(ready_client, str(tmp_path / "x.mov"))
    cid = media.list_media(ready_client)[0]["id"]
    out = media.tag_clips(ready_client, [cid, "clip-9999"], color="Red")
    assert out["tagged"] == [cid]
    assert out["failed"][0]["clipId"] == "clip-9999"
    # the good one stays tagged
    assert "Red" in media.list_media(ready_client)[0]["flags"]


def test_tag_invalid_color_raises(ready_client) -> None:
    with pytest.raises(ValidationError):
        media.tag_clips(ready_client, ["any"], color="Periwinkle")


def test_tag_empty_clip_ids_raises(ready_client) -> None:
    with pytest.raises(ValidationError):
        media.tag_clips(ready_client, [], color="Green")

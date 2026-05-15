"""`dvr timeline delete <name>` — v0.2.2."""
from __future__ import annotations

import pytest

from dvr.commands import project as proj_cmd
from dvr.commands import timeline as tl_cmd
from dvr.errors import ApiCallFailed, NotFound, ValidationError


@pytest.fixture
def ready(fake_client):
    proj_cmd.new_project(fake_client, "demo")
    tl_cmd.new_timeline(fake_client, "Main")
    tl_cmd.new_timeline(fake_client, "Alt")
    return fake_client


def test_delete_existing_timeline(ready, fake_resolve) -> None:
    out = tl_cmd.delete_timeline(ready, "Alt")
    assert out == {"ok": True, "name": "Alt"}
    names = {t["name"] for t in tl_cmd.list_timelines(ready)}
    assert names == {"Main"}


def test_delete_current_timeline_updates_current(ready, fake_resolve) -> None:
    # After fixture, current is "Alt" (created last). Delete it.
    tl_cmd.delete_timeline(ready, "Alt")
    cur = tl_cmd.current_timeline(ready)
    assert cur["name"] == "Main"


def test_delete_missing_timeline_raises(ready) -> None:
    with pytest.raises(NotFound):
        tl_cmd.delete_timeline(ready, "ghost")


def test_delete_empty_name_raises(ready) -> None:
    with pytest.raises(ValidationError):
        tl_cmd.delete_timeline(ready, "  ")


def test_delete_dry_run_does_not_mutate(ready) -> None:
    out = tl_cmd.delete_timeline(ready, "Alt", dry_run=True)
    assert out["dryRun"] is True
    assert out["planned"][0]["action"] == "timeline.delete"
    assert {t["name"] for t in tl_cmd.list_timelines(ready)} == {"Main", "Alt"}


def test_delete_only_timeline_clears_current(fake_client) -> None:
    proj_cmd.new_project(fake_client, "solo")
    tl_cmd.new_timeline(fake_client, "Only")
    tl_cmd.delete_timeline(fake_client, "Only")
    with pytest.raises(ValidationError):
        tl_cmd.current_timeline(fake_client)

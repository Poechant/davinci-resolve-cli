"""V2 AC15/AC16/AC17 — timeline cut/move via WI bridge."""
from __future__ import annotations

from typing import Any

import pytest

from dvr.commands import project as proj_cmd
from dvr.commands import timeline as tl_cmd
from dvr.errors import WIError, WIUnavailable


class _FakeBridge:
    def __init__(self, *, raise_exc: Exception | None = None, result: Any = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.raise_exc = raise_exc
        self.result = result

    def call(self, method: str, params: dict) -> Any:  # noqa: D401
        self.calls.append((method, params))
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.result


@pytest.fixture
def ready(fake_client):
    proj_cmd.new_project(fake_client, "demo")
    tl_cmd.new_timeline(fake_client, "Main")
    return fake_client


def test_cut_dry_run_does_not_call_bridge(ready) -> None:
    bridge = _FakeBridge()
    out = tl_cmd.cut_at(ready, at="00:00:02:00", dry_run=True, bridge=bridge)
    assert out["dryRun"] is True
    assert out["planned"][0]["action"] == "timeline.cut"
    assert out["planned"][0]["frame"] == 48
    assert bridge.calls == []


def test_cut_calls_bridge_with_at_param(ready) -> None:
    bridge = _FakeBridge(result={"ok": True, "frame": 48, "note": "placeholder marker added"})
    out = tl_cmd.cut_at(ready, at="00:00:02:00", bridge=bridge)
    assert bridge.calls == [("timeline.cut", {"at": "00:00:02:00"})]
    assert out["timecode"] == "00:00:02:00"
    assert out["frame"] == 48
    assert out["note"] == "placeholder marker added"


def test_cut_invalid_timecode(ready) -> None:
    bridge = _FakeBridge()
    with pytest.raises(ValueError):
        tl_cmd.cut_at(ready, at="bogus", bridge=bridge)


def test_cut_propagates_wi_unavailable(ready) -> None:
    bridge = _FakeBridge(raise_exc=WIUnavailable("no plugin"))
    with pytest.raises(WIUnavailable):
        tl_cmd.cut_at(ready, at="00:00:02:00", bridge=bridge)


def test_cut_propagates_wi_error(ready) -> None:
    bridge = _FakeBridge(raise_exc=WIError("plugin sad", hint="check plugin"))
    with pytest.raises(WIError):
        tl_cmd.cut_at(ready, at="00:00:02:00", bridge=bridge)


def test_move_dry_run(ready) -> None:
    bridge = _FakeBridge()
    out = tl_cmd.move_clip(ready, clip_id="clip-1", to="00:00:05:00", dry_run=True, bridge=bridge)
    assert out["dryRun"] is True
    assert out["planned"][0]["clipId"] == "clip-1"
    assert out["planned"][0]["frame"] == 120
    assert bridge.calls == []


def test_move_calls_bridge_with_clip_and_to(ready) -> None:
    bridge = _FakeBridge(result={"deferred": "v0.3"})
    out = tl_cmd.move_clip(ready, clip_id="clip-1", to="00:00:05:00", bridge=bridge)
    assert bridge.calls == [("timeline.move", {"clipId": "clip-1", "to": "00:00:05:00"})]
    assert out["frame"] == 120
    assert out["deferred"] == "v0.3"


def test_cut_without_open_timeline(fake_client) -> None:
    proj_cmd.new_project(fake_client, "empty")
    bridge = _FakeBridge()
    with pytest.raises(Exception):  # ValidationError, no timeline
        tl_cmd.cut_at(fake_client, at="00:00:02:00", bridge=bridge)

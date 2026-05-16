"""AC9 / AC10 / AC11 — render presets / submit / status / list / wait / cancel."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.commands import project as proj_cmd
from dvr.commands import render
from dvr.errors import NotFound, ValidationError
from dvr.jobs.store import JobStore

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "render.json"


def _schemas() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(path=tmp_path / "jobs.json")


@pytest.fixture
def ready(fake_client, fake_resolve):
    proj_cmd.new_project(fake_client, "demo")
    return fake_client


# ---------- presets ----------

def test_presets_lists_available(ready) -> None:
    out = render.list_presets(ready)
    assert "H.264 Master" in out
    jsonschema.validate(out, _schemas()["$defs"]["PresetList"])


def test_presets_without_project_raises(fake_client) -> None:
    with pytest.raises(ValidationError):
        render.list_presets(fake_client)


# ---------- submit ----------

def test_submit_returns_job_id_and_is_queued(ready, store) -> None:
    out = render.submit_render(
        ready, preset="H.264 Master", timeline="cur", output="/tmp/x.mp4", store=store
    )
    assert out["status"] == "queued"
    assert out["jobId"].startswith("job-")
    assert out["preset"] == "H.264 Master"
    jsonschema.validate(out, _schemas()["$defs"]["SubmitResult"])
    persisted = store.get(out["jobId"])
    assert persisted is not None and persisted.preset == "H.264 Master"


def test_submit_with_start_flag_marks_rendering(ready, store) -> None:
    out = render.submit_render(
        ready, preset="H.264 Master", output="/tmp/x.mp4", start=True, store=store
    )
    assert out["status"] == "rendering"
    assert store.get(out["jobId"]).status == "rendering"


def test_submit_unknown_preset_raises(ready, store) -> None:
    with pytest.raises(ValidationError):
        render.submit_render(
            ready, preset="WeirdoPreset", output="/tmp/x.mp4", store=store
        )


def test_submit_unknown_preset_hint_suggests_close_match(ready, store) -> None:
    """A close-but-wrong preset name should trigger the fuzzy-match hint."""
    with pytest.raises(ValidationError) as exc:
        render.submit_render(
            ready, preset="H264 Master", output="/tmp/x.mp4", store=store
        )
    # FakeProject preloads "H.264 Master" + "ProRes 422 HQ"; fuzzy should find one.
    assert exc.value.hint is not None
    assert "Did you mean" in exc.value.hint
    assert "H.264 Master" in exc.value.hint


# ---------- status ----------

def test_status_reads_live_state(ready, store, fake_resolve) -> None:
    out = render.submit_render(
        ready, preset="H.264 Master", output="/tmp/x.mp4", store=store
    )
    fake_resolve.GetProjectManager().GetCurrentProject()._force_job_status(
        out["jobId"], "Rendering", 50
    )
    info = render.get_status(ready, out["jobId"], store=store)
    assert info["status"] == "rendering"
    assert info["progress"] == 50
    jsonschema.validate(info, _schemas()["$defs"]["StatusResult"])


def test_status_unknown_job_raises(ready, store) -> None:
    with pytest.raises(NotFound):
        render.get_status(ready, "ghost", store=store)


# ---------- list ----------

def test_list_merges_local_and_live(ready, store, fake_resolve) -> None:
    sub = render.submit_render(ready, preset="H.264 Master", output="/tmp/a.mp4", store=store)
    fake_resolve.GetProjectManager().GetCurrentProject()._force_job_status(
        sub["jobId"], "Complete", 100
    )
    out = render.list_jobs(ready, store=store)
    jsonschema.validate(out, _schemas()["$defs"]["JobList"])
    row = next(r for r in out if r["jobId"] == sub["jobId"])
    assert row["status"] == "completed"
    assert row["progress"] == 100


# ---------- cancel ----------

def test_cancel_marks_cancelled(ready, store) -> None:
    sub = render.submit_render(
        ready, preset="H.264 Master", output="/tmp/x.mp4", start=True, store=store
    )
    out = render.cancel_job(ready, sub["jobId"], store=store)
    assert out == {"jobId": sub["jobId"], "status": "cancelled"}
    assert store.get(sub["jobId"]).status == "cancelled"


def test_cancel_unknown_raises(ready, store) -> None:
    with pytest.raises(NotFound):
        render.cancel_job(ready, "ghost", store=store)


# ---------- wait ----------

def test_wait_returns_immediately_when_terminal(ready, store, fake_resolve) -> None:
    sub = render.submit_render(ready, preset="H.264 Master", output="/tmp/x.mp4", store=store)
    fake_resolve.GetProjectManager().GetCurrentProject()._force_job_status(
        sub["jobId"], "Complete", 100
    )
    calls: list[float] = []

    def sleeper(s: float) -> None:
        calls.append(s)

    out = render.wait_job(ready, sub["jobId"], interval=0.1, store=store, sleeper=sleeper)
    assert out["status"] == "completed"
    assert calls == []  # no sleeps needed


def test_wait_polls_until_terminal(ready, store, fake_resolve) -> None:
    sub = render.submit_render(ready, preset="H.264 Master", output="/tmp/x.mp4", store=store)
    project = fake_resolve.GetProjectManager().GetCurrentProject()
    transitions = [("Rendering", 25), ("Rendering", 75), ("Complete", 100)]
    project._force_job_status(sub["jobId"], "Ready", 0)

    def sleeper(_s: float) -> None:
        if transitions:
            status, prog = transitions.pop(0)
            project._force_job_status(sub["jobId"], status, prog)

    progress_log: list[dict] = []
    out = render.wait_job(
        ready, sub["jobId"], interval=0.0, store=store, sleeper=sleeper,
        progress_sink=lambda info: progress_log.append(info),
    )
    assert out["status"] == "completed"
    assert out["progress"] == 100
    assert any(p["progress"] == 25 for p in progress_log)


def test_wait_respects_timeout(ready, store, fake_resolve) -> None:
    sub = render.submit_render(ready, preset="H.264 Master", output="/tmp/x.mp4", store=store)
    fake_resolve.GetProjectManager().GetCurrentProject()._force_job_status(
        sub["jobId"], "Rendering", 10
    )

    def sleeper(_s: float) -> None:
        pass

    out = render.wait_job(
        ready, sub["jobId"], interval=0.0, timeout=-1.0, store=store, sleeper=sleeper
    )
    assert out.get("timedOut") is True

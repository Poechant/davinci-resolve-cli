"""`dvr render ...` — async render job lifecycle.

`submit` is non-blocking: AddRenderJob → write to ~/.dvr/jobs.json → return jobId.
`status`/`list`/`wait`/`cancel` operate on Resolve's job list, projected through
the local store so we can report on cancelled/completed jobs even if Resolve
has been restarted.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import typer

from ..errors import ApiCallFailed, NotFound, ValidationError
from ..jobs.store import JobRecord, JobStore, default_store_path, now_iso
from ..output import emit, resolve_format
from ..resolve import ResolveClient
from . import _client as client_mod

app = typer.Typer(help="Render queue management (async jobs).")


def _current_project_or_raise(client: ResolveClient):
    proj = client.project_manager().GetCurrentProject()
    if proj is None:
        raise ValidationError("no project is currently open")
    return proj


# Maps Resolve's JobStatus strings to our normalized status enum.
_RESOLVE_STATUS_MAP = {
    "Ready": "queued",
    "Rendering": "rendering",
    "Complete": "completed",
    "Completed": "completed",
    "Failed": "failed",
    "Cancelled": "cancelled",
    "Canceled": "cancelled",
}


def _normalize_status(resolve_status: str) -> str:
    return _RESOLVE_STATUS_MAP.get(resolve_status, resolve_status.lower() or "queued")


# ---------- pure helpers ----------

def list_presets(client: ResolveClient) -> list[str]:
    proj = _current_project_or_raise(client)
    return list(proj.GetRenderPresetList() or [])


def submit_render(
    client: ResolveClient,
    *,
    preset: str,
    timeline: Optional[str] = None,
    output: str,
    start: bool = False,
    store: Optional[JobStore] = None,
) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    presets = proj.GetRenderPresetList() or []
    if preset not in presets:
        # Fuzzy-match against known presets to provide an actionable hint.
        from difflib import get_close_matches
        close = get_close_matches(preset, presets, n=5, cutoff=0.4)
        suggestion = (
            f" Did you mean one of: {', '.join(repr(c) for c in close)}?"
            if close
            else ""
        )
        raise ValidationError(
            f"unknown render preset: {preset}",
            hint=f"Use `dvr render presets` to list available presets.{suggestion}",
        )
    if not proj.LoadRenderPreset(preset):
        raise ApiCallFailed("LoadRenderPreset", preset)

    out_path = Path(output).expanduser()
    target_dir = str(out_path.parent)
    target_name = out_path.name
    if not proj.SetRenderSettings({"TargetDir": target_dir, "CustomName": target_name}):
        raise ApiCallFailed("SetRenderSettings")

    job_id = proj.AddRenderJob()
    if not job_id:
        raise ApiCallFailed("AddRenderJob")

    record = JobRecord(
        jobId=job_id,
        project=proj.GetName(),
        timeline=timeline or "",
        preset=preset,
        output=str(out_path),
        submittedAt=now_iso(),
        status="queued",
        progress=0,
    )
    (store or JobStore()).add(record)

    if start:
        if not proj.StartRendering([job_id]):
            raise ApiCallFailed("StartRendering")
        (store or JobStore()).update(job_id, status="rendering")

    return {
        "jobId": job_id,
        "status": "rendering" if start else "queued",
        "submittedAt": record.submittedAt,
        "preset": preset,
        "timeline": timeline or "",
        "output": str(out_path),
    }


def get_status(
    client: ResolveClient,
    job_id: str,
    *,
    store: Optional[JobStore] = None,
) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    store = store or JobStore()
    record = store.get(job_id)
    raw = proj.GetRenderJobStatus(job_id) or {}
    if not record and not raw:
        raise NotFound("RenderJob", job_id)
    status = _normalize_status(raw.get("JobStatus")) if raw.get("JobStatus") else (record.status if record else "queued")
    progress = int(raw.get("CompletionPercentage", record.progress if record else 0) or 0)
    if record:
        store.update(job_id, status=status, progress=progress)
    return {"jobId": job_id, "status": status, "progress": progress}


def list_jobs(
    client: ResolveClient,
    *,
    store: Optional[JobStore] = None,
) -> list[dict[str, Any]]:
    proj = _current_project_or_raise(client)
    store = store or JobStore()
    by_id: dict[str, dict[str, Any]] = {}
    # local store first
    for rec in store.list_all():
        by_id[rec.jobId] = {
            "jobId": rec.jobId,
            "status": rec.status,
            "progress": rec.progress,
            "preset": rec.preset,
            "timeline": rec.timeline,
            "output": rec.output,
            "submittedAt": rec.submittedAt,
        }
    # overlay with live Resolve state
    for live in proj.GetRenderJobList() or []:
        jid = live.get("JobId")
        if not jid:
            continue
        row = by_id.setdefault(
            jid,
            {"jobId": jid, "status": "queued", "progress": 0},
        )
        row["status"] = _normalize_status(live.get("JobStatus", "Ready"))
        row["progress"] = int(live.get("CompletionPercentage", 0) or 0)
    return list(by_id.values())


def cancel_job(
    client: ResolveClient,
    job_id: str,
    *,
    store: Optional[JobStore] = None,
) -> dict[str, Any]:
    proj = _current_project_or_raise(client)
    store = store or JobStore()
    if not store.get(job_id) and not proj.GetRenderJobStatus(job_id):
        raise NotFound("RenderJob", job_id)
    # stop any active rendering then delete the entry
    try:
        proj.StopRendering()
    except Exception:  # noqa: BLE001
        pass
    proj.DeleteRenderJob(job_id)
    store.update(job_id, status="cancelled")
    return {"jobId": job_id, "status": "cancelled"}


def wait_job(
    client: ResolveClient,
    job_id: str,
    *,
    interval: float = 1.0,
    timeout: Optional[float] = None,
    store: Optional[JobStore] = None,
    sleeper=time.sleep,
    progress_sink=None,
) -> dict[str, Any]:
    """Poll until job reaches a terminal state. Progress events go to `progress_sink`."""
    terminal = {"completed", "failed", "cancelled"}
    start = time.monotonic()
    last_progress = -1
    while True:
        info = get_status(client, job_id, store=store)
        if progress_sink is not None and info["progress"] != last_progress:
            progress_sink(info)
            last_progress = info["progress"]
        if info["status"] in terminal:
            return info
        if timeout is not None and (time.monotonic() - start) > timeout:
            return {**info, "timedOut": True}
        sleeper(interval)


# ---------- typer wrappers ----------

@app.command("presets")
def cli_presets(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """List render presets available for the current project."""
    emit(list_presets(client_mod.get()), resolve_format(fmt))


@app.command("submit")
def cli_submit(
    preset: str = typer.Option(..., "--preset", "-p"),
    output: str = typer.Option(..., "--output", "-o"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t"),
    start: bool = typer.Option(False, "--start", help="Start rendering immediately after queueing."),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Queue a render job. Returns a jobId immediately (non-blocking)."""
    emit(
        submit_render(
            client_mod.get(), preset=preset, timeline=timeline, output=output, start=start
        ),
        resolve_format(fmt),
    )


@app.command("status")
def cli_status(
    job_id: str,
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Show status of a single render job."""
    emit(get_status(client_mod.get(), job_id), resolve_format(fmt))


@app.command("list")
def cli_list(fmt: Optional[str] = typer.Option(None, "--format", "-f")) -> None:
    """List all render jobs (local store ∪ Resolve queue)."""
    emit(list_jobs(client_mod.get()), resolve_format(fmt))


@app.command("wait")
def cli_wait(
    job_id: str,
    interval: float = typer.Option(1.0, "--interval", "-i"),
    timeout: Optional[float] = typer.Option(None, "--timeout"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Block until the job finishes. Progress is written to stderr."""
    def _stderr(info: dict[str, Any]) -> None:
        sys.stderr.write(f"[render {info['jobId']}] {info['status']} {info['progress']}%\n")
        sys.stderr.flush()

    emit(
        wait_job(client_mod.get(), job_id, interval=interval, timeout=timeout, progress_sink=_stderr),
        resolve_format(fmt),
    )


@app.command("cancel")
def cli_cancel(
    job_id: str,
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Cancel a queued or running render job."""
    emit(cancel_job(client_mod.get(), job_id), resolve_format(fmt))

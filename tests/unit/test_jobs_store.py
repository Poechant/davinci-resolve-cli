"""Storage layer for render jobs."""
from __future__ import annotations

from pathlib import Path

import pytest

from dvr.jobs.store import JobRecord, JobStore, now_iso


@pytest.fixture
def store(tmp_path: Path) -> JobStore:
    return JobStore(path=tmp_path / "jobs.json")


def _make(job_id: str = "job-1") -> JobRecord:
    return JobRecord(
        jobId=job_id, project="demo", timeline="tl", preset="H.264", output="/tmp/x.mp4",
        submittedAt=now_iso(),
    )


def test_empty_store(store: JobStore) -> None:
    assert store.list_all() == []
    assert store.get("ghost") is None


def test_add_then_get(store: JobStore) -> None:
    rec = _make()
    store.add(rec)
    got = store.get("job-1")
    assert got is not None
    assert got.jobId == "job-1"
    assert got.preset == "H.264"


def test_add_persists_across_instances(tmp_path: Path) -> None:
    s1 = JobStore(path=tmp_path / "jobs.json")
    s1.add(_make())
    s2 = JobStore(path=tmp_path / "jobs.json")
    assert s2.get("job-1") is not None


def test_update_changes_fields(store: JobStore) -> None:
    store.add(_make())
    updated = store.update("job-1", status="rendering", progress=42)
    assert updated is not None
    assert updated.status == "rendering"
    assert updated.progress == 42
    again = store.get("job-1")
    assert again is not None and again.progress == 42


def test_update_unknown_returns_none(store: JobStore) -> None:
    assert store.update("ghost", status="cancelled") is None


def test_update_rejects_invalid_status(store: JobStore) -> None:
    store.add(_make())
    with pytest.raises(ValueError):
        store.update("job-1", status="exploded")


def test_remove(store: JobStore) -> None:
    store.add(_make())
    assert store.remove("job-1") is True
    assert store.get("job-1") is None
    assert store.remove("job-1") is False


def test_list_returns_all(store: JobStore) -> None:
    store.add(_make("a"))
    store.add(_make("b"))
    ids = {r.jobId for r in store.list_all()}
    assert ids == {"a", "b"}

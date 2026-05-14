"""On-disk render job store: ~/.dvr/jobs.json.

A flat JSON list of records keyed by Resolve's internal jobId. We keep the
schema permissive so v0.2 can add columns without breaking existing files.

File lock semantics:
- atomic write via temp + os.replace
- shared advisory lock via fcntl (POSIX) when available
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None  # type: ignore[assignment]


def default_store_path() -> Path:
    base = Path(os.environ.get("DVR_HOME", str(Path.home() / ".dvr")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "jobs.json"


@dataclass
class JobRecord:
    jobId: str
    project: str
    timeline: str
    preset: str
    output: str
    submittedAt: str
    status: str = "queued"
    progress: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


VALID_STATUSES = {"queued", "rendering", "completed", "failed", "cancelled"}


class JobStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or default_store_path()

    # ---------- low level ----------

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
            try:
                content = fh.read().strip()
                return json.loads(content) if content else []
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _write(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="jobs.", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                json.dump(records, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # ---------- high level ----------

    def add(self, record: JobRecord) -> None:
        rows = self._read()
        rows.append(asdict(record))
        self._write(rows)

    def get(self, job_id: str) -> Optional[JobRecord]:
        for row in self._read():
            if row.get("jobId") == job_id:
                return JobRecord(**{**row, "extra": row.get("extra") or {}})
        return None

    def list_all(self) -> list[JobRecord]:
        return [JobRecord(**{**r, "extra": r.get("extra") or {}}) for r in self._read()]

    def update(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> Optional[JobRecord]:
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        rows = self._read()
        target: Optional[dict[str, Any]] = None
        for row in rows:
            if row.get("jobId") == job_id:
                if status is not None:
                    row["status"] = status
                if progress is not None:
                    row["progress"] = progress
                target = row
                break
        if target is None:
            return None
        self._write(rows)
        return JobRecord(**{**target, "extra": target.get("extra") or {}})

    def remove(self, job_id: str) -> bool:
        rows = self._read()
        new_rows = [r for r in rows if r.get("jobId") != job_id]
        if len(new_rows) == len(rows):
            return False
        self._write(new_rows)
        return True


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

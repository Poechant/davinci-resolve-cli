from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DvrError(Exception):
    error_code: str
    message: str
    hint: Optional[str] = None
    exit_code: int = 1

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"errorCode": self.error_code, "message": self.message}
        if self.hint:
            d["hint"] = self.hint
        return d


class ResolveNotRunning(DvrError):
    def __init__(self, hint: Optional[str] = None) -> None:
        super().__init__(
            error_code="resolve_not_running",
            message="DaVinci Resolve is not running or not reachable.",
            hint=hint or "Launch DaVinci Resolve and ensure External scripting is enabled "
            "(Preferences → System → General → External scripting using = Local).",
            exit_code=2,
        )


class VersionUnsupported(DvrError):
    def __init__(self, detected: str) -> None:
        super().__init__(
            error_code="version_unsupported",
            message=f"DaVinci Resolve version {detected} is below the supported minimum (18.0).",
            hint="Upgrade to DaVinci Resolve 18 or later.",
            exit_code=1,
        )


class ApiUnavailable(DvrError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            error_code="api_unavailable",
            message=f"DaVinciResolveScript API could not be loaded: {reason}",
            hint="Verify install path and RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB env vars. "
            "Run `dvr doctor` for details.",
            exit_code=2,
        )


class ApiCallFailed(DvrError):
    def __init__(self, op: str, detail: Optional[str] = None) -> None:
        super().__init__(
            error_code="api_call_failed",
            message=f"DaVinci Resolve API call failed: {op}" + (f" ({detail})" if detail else ""),
            hint="The API returned False/None. Confirm preconditions (project open, "
            "timeline selected, file path valid).",
            exit_code=3,
        )


class ValidationError(DvrError):
    def __init__(self, message: str, hint: Optional[str] = None) -> None:
        super().__init__(
            error_code="validation_error",
            message=message,
            hint=hint,
            exit_code=1,
        )


class NotFound(DvrError):
    def __init__(self, kind: str, identifier: str) -> None:
        super().__init__(
            error_code="not_found",
            message=f"{kind} not found: {identifier}",
            hint=f"Use `dvr {kind.lower()} list` to see available items.",
            exit_code=1,
        )

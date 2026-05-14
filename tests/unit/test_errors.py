"""AC3 / AC18 — structured errors, error codes, exit codes."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from dvr.errors import (
    ApiCallFailed,
    ApiUnavailable,
    DvrError,
    NotFound,
    ResolveNotRunning,
    ValidationError,
    VersionUnsupported,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "error.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@pytest.mark.parametrize(
    "exc,expected_code,expected_exit",
    [
        (ResolveNotRunning(), "resolve_not_running", 2),
        (VersionUnsupported("17.4"), "version_unsupported", 1),
        (ApiUnavailable("missing fusionscript"), "api_unavailable", 2),
        (ApiCallFailed("LoadProject"), "api_call_failed", 3),
        (ValidationError("must be int"), "validation_error", 1),
        (NotFound("Project", "demo"), "not_found", 1),
    ],
)
def test_error_codes_and_exit_codes(exc: DvrError, expected_code: str, expected_exit: int) -> None:
    assert exc.error_code == expected_code
    assert exc.exit_code == expected_exit


@pytest.mark.parametrize(
    "exc",
    [
        ResolveNotRunning(),
        VersionUnsupported("17.4"),
        ApiUnavailable("missing"),
        ApiCallFailed("op"),
        ValidationError("x"),
        NotFound("Project", "y"),
    ],
)
def test_error_payload_matches_schema(exc: DvrError) -> None:
    jsonschema.validate(exc.to_dict(), _schema())


def test_error_payload_has_errorCode_and_message() -> None:
    err = ResolveNotRunning()
    payload = err.to_dict()
    assert "errorCode" in payload
    assert "message" in payload


def test_hint_is_optional() -> None:
    plain = DvrError("custom", "msg")
    payload = plain.to_dict()
    assert "hint" not in payload

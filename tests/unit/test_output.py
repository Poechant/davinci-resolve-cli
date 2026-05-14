"""AC16 — --format / DVR_OUTPUT / TTY behavior."""
from __future__ import annotations

import json

import pytest
import yaml

from dvr.output import OutputFormat, render, resolve_format


def test_explicit_flag_wins() -> None:
    assert resolve_format("json", env={"DVR_OUTPUT": "yaml"}, is_tty=True) is OutputFormat.JSON
    assert resolve_format("yaml", env={}, is_tty=False) is OutputFormat.YAML


def test_env_overrides_tty_default() -> None:
    assert resolve_format(None, env={"DVR_OUTPUT": "yaml"}, is_tty=True) is OutputFormat.YAML
    assert resolve_format(None, env={"DVR_OUTPUT": "json"}, is_tty=True) is OutputFormat.JSON


def test_tty_default_is_table_non_tty_is_json() -> None:
    assert resolve_format(None, env={}, is_tty=True) is OutputFormat.TABLE
    assert resolve_format(None, env={}, is_tty=False) is OutputFormat.JSON


def test_unknown_format_raises() -> None:
    with pytest.raises(ValueError):
        resolve_format("xml", env={}, is_tty=True)
    with pytest.raises(ValueError):
        resolve_format(None, env={"DVR_OUTPUT": "xml"}, is_tty=True)


def test_render_json_is_valid_json() -> None:
    out = render({"a": 1, "b": [1, 2]}, OutputFormat.JSON)
    assert json.loads(out) == {"a": 1, "b": [1, 2]}


def test_render_yaml_is_valid_yaml() -> None:
    out = render([{"name": "x"}], OutputFormat.YAML)
    assert yaml.safe_load(out) == [{"name": "x"}]


def test_render_table_handles_list_of_dicts() -> None:
    out = render([{"name": "a", "fps": 24}, {"name": "b", "fps": 30}], OutputFormat.TABLE)
    assert "name" in out and "a" in out and "b" in out


def test_render_table_handles_dict() -> None:
    out = render({"name": "demo", "fps": 24}, OutputFormat.TABLE)
    assert "name" in out and "demo" in out


def test_render_table_empty_list() -> None:
    out = render([], OutputFormat.TABLE)
    assert "empty" in out.lower()

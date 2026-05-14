"""Output rendering: table (rich) / json / yaml, with TTY auto-detection."""
from __future__ import annotations

import json
import os
import sys
from enum import Enum
from typing import Any, Optional


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"


VALID_FORMATS = {f.value for f in OutputFormat}


def resolve_format(
    explicit: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    is_tty: Optional[bool] = None,
) -> OutputFormat:
    """Resolution order: explicit flag → DVR_OUTPUT env → TTY default.

    TTY → table, non-TTY → json.
    """
    if explicit:
        explicit_l = explicit.lower()
        if explicit_l not in VALID_FORMATS:
            raise ValueError(f"unknown format: {explicit}")
        return OutputFormat(explicit_l)
    env = env if env is not None else dict(os.environ)
    env_val = env.get("DVR_OUTPUT")
    if env_val:
        env_l = env_val.lower()
        if env_l not in VALID_FORMATS:
            raise ValueError(f"unknown DVR_OUTPUT value: {env_val}")
        return OutputFormat(env_l)
    if is_tty is None:
        is_tty = sys.stdout.isatty()
    return OutputFormat.TABLE if is_tty else OutputFormat.JSON


def render(data: Any, fmt: OutputFormat) -> str:
    if fmt is OutputFormat.JSON:
        return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)
    if fmt is OutputFormat.YAML:
        import yaml  # local import to keep startup fast

        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    return _render_table(data)


def emit(data: Any, fmt: OutputFormat, stream=None) -> None:
    stream = stream or sys.stdout
    stream.write(render(data, fmt))
    if fmt in (OutputFormat.JSON, OutputFormat.YAML) and not render(data, fmt).endswith("\n"):
        stream.write("\n")


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _render_table(data: Any) -> str:
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True, force_terminal=False)
    if isinstance(data, list):
        if not data:
            console.print("(empty)")
        elif all(isinstance(row, dict) for row in data):
            table = Table(show_header=True, header_style="bold")
            columns = list(data[0].keys())
            for col in columns:
                table.add_column(col)
            for row in data:
                table.add_row(*[_cell(row.get(c)) for c in columns])
            console.print(table)
        else:
            for row in data:
                console.print(_cell(row))
    elif isinstance(data, dict):
        table = Table(show_header=False)
        table.add_column("field", style="bold")
        table.add_column("value")
        for k, v in data.items():
            table.add_row(str(k), _cell(v))
        console.print(table)
    else:
        console.print(_cell(data))
    return console.export_text()


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, (list, tuple)):
        return ", ".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

"""V2 AC8/AC9/AC10/AC11 — MCP server tool registry + dispatch + error mapping."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import jsonschema
import pytest

from dvr.commands import project as proj_cmd
from dvr.errors import ResolveNotRunning
from dvr.mcp import server as mcp_server
from dvr.mcp import tools as mcp_tools


# ---------- registry shape ----------

def test_registry_has_at_least_12_tools() -> None:
    specs = mcp_tools.build_registry()
    assert len(specs) >= 12


def test_registry_covers_all_domains() -> None:
    names = set(mcp_tools.names())
    assert "doctor" in names
    assert any(n.startswith("project.") for n in names)
    assert any(n.startswith("media.") for n in names)
    assert any(n.startswith("render.") for n in names)
    assert any(n.startswith("timeline.") for n in names)


def test_every_tool_has_valid_input_schema() -> None:
    for spec in mcp_tools.build_registry():
        # Each input_schema must itself be a valid JSON Schema
        jsonschema.Draft202012Validator.check_schema(spec.input_schema)


# ---------- server build ----------

def _build_with(client) -> mcp_server.Server:
    return mcp_server.build_server(client_factory=lambda: client)


def test_build_server_returns_named_server(fake_client) -> None:
    srv = _build_with(fake_client)
    assert srv.name == mcp_server.SERVER_NAME


# ---------- list_tools through real MCP RequestContext ----------

async def _list_tools(server) -> list:
    # Direct handler lookup; the MCP SDK stores them on the server's request handlers
    from mcp import types as T
    handler = server.request_handlers[T.ListToolsRequest]
    req = T.ListToolsRequest(method="tools/list", params=None)
    result = await handler(req)
    return result.root.tools


async def _call_tool(server, name: str, args: dict) -> list:
    from mcp import types as T
    handler = server.request_handlers[T.CallToolRequest]
    req = T.CallToolRequest(
        method="tools/call",
        params=T.CallToolRequestParams(name=name, arguments=args or {}),
    )
    result = await handler(req)
    return result.root.content, getattr(result.root, "isError", False)


def test_list_tools_returns_full_registry(fake_client) -> None:
    server = _build_with(fake_client)
    tools = asyncio.run(_list_tools(server))
    assert len(tools) == len(mcp_tools.build_registry())
    assert "doctor" in {t.name for t in tools}


def test_call_doctor_works_without_live_resolve() -> None:
    # doctor is needs_resolve=False so it shouldn't even hit the factory
    server = mcp_server.build_server(client_factory=lambda: (_ for _ in ()).throw(AssertionError("should not be called")))
    content, is_error = asyncio.run(_call_tool(server, "doctor", {}))
    assert is_error is False
    payload = json.loads(content[0].text)
    assert "bridgeStatus" in payload


def test_call_project_list_empty(fake_client) -> None:
    server = _build_with(fake_client)
    content, is_error = asyncio.run(_call_tool(server, "project.list", {}))
    assert is_error is False
    assert json.loads(content[0].text) == []


def test_call_project_new_then_list(fake_client) -> None:
    server = _build_with(fake_client)
    asyncio.run(_call_tool(server, "project.new", {"name": "demo"}))
    content, _ = asyncio.run(_call_tool(server, "project.list", {}))
    items = json.loads(content[0].text)
    assert {i["name"] for i in items} == {"demo"}


# ---------- error mapping ----------

def test_dvr_error_surfaces_as_structured_payload(fake_client) -> None:
    server = _build_with(fake_client)
    # `project.current` raises ValidationError when no project is open
    content, is_error = asyncio.run(_call_tool(server, "project.current", {}))
    payload = json.loads(content[0].text)
    assert payload["errorCode"] == "validation_error"
    assert "message" in payload


def test_unknown_tool_raises(fake_client) -> None:
    server = _build_with(fake_client)
    content, _ = asyncio.run(_call_tool(server, "ghost.nope", {}))
    payload = json.loads(content[0].text)
    assert payload["errorCode"] == "unknown_tool"


# ---------- doctor structure ----------

def test_doctor_tool_schema_matches_v01_schema() -> None:
    schema = json.loads((Path(__file__).resolve().parents[2] / "src" / "dvr" / "schemas" / "doctor.json").read_text())
    server = mcp_server.build_server(client_factory=lambda: None)
    content, _ = asyncio.run(_call_tool(server, "doctor", {}))
    jsonschema.validate(json.loads(content[0].text), schema)

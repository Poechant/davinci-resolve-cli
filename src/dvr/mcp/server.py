"""MCP server (stdio) — exposes the v0.1 command surface to any MCP client.

Wire format: each tool's result is JSON-stringified and returned as a single
TextContent. Errors propagate as MCP `isError: true` with a TextContent
whose body is the canonical DvrError payload (errorCode/message/hint).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Optional

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .. import __version__
from ..commands import _client as client_mod
from ..errors import DvrError
from ..resolve import ResolveClient
from . import tools as tools_mod


SERVER_NAME = "davinci-resolve-cli"


def _serialize(result: Any) -> str:
    """JSON-encode the tool result. Handles dataclasses and Path-likes."""

    def default(o: Any) -> Any:
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(result, ensure_ascii=False, indent=2, default=default)


def _error_content(err: DvrError) -> list[types.TextContent]:
    payload = err.to_dict()
    return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


def _internal_error(exc: Exception) -> list[types.TextContent]:
    payload = {
        "errorCode": "internal_error",
        "message": f"unexpected error: {exc}",
    }
    return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


def build_server(
    *,
    client_factory: Optional[Callable[[], ResolveClient]] = None,
) -> Server:
    """Construct an MCP `Server` with all tools wired up.

    Tests pass a `client_factory` returning a FakeResolveClient so they can
    exercise tool handlers without launching Resolve.
    """
    server: Server = Server(SERVER_NAME, version=__version__)
    registry = tools_mod.build_registry()
    spec_by_name = {t.name: t for t in registry}

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t.name,
                description=t.description,
                inputSchema=t.input_schema,
            )
            for t in registry
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        spec = spec_by_name.get(name)
        if spec is None:
            return _error_content(
                DvrError(
                    error_code="unknown_tool",
                    message=f"unknown tool: {name}",
                    hint=f"Available tools: {', '.join(spec_by_name)}",
                )
            )
        try:
            if spec.needs_resolve:
                client = (client_factory or client_mod.get)()
            else:
                client = None  # doctor doesn't need a live client
            result = spec.handler(client, arguments or {})
        except DvrError as err:
            # MCP framework will mark this as isError; we surface the structured payload
            return _error_content(err)
        return [types.TextContent(type="text", text=_serialize(result))]

    return server


def serve_stdio() -> None:
    """Synchronous entrypoint used by `dvr mcp`."""
    asyncio.run(_run_stdio())


async def _run_stdio() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

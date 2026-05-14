"""`dvr mcp` — start a stdio MCP server."""
from __future__ import annotations

import typer

from ..mcp.server import serve_stdio

app = typer.Typer(help="MCP server (stdio transport). Wire it into any MCP-aware AI agent.")


@app.callback(invoke_without_command=True)
def mcp_serve() -> None:
    """Start the stdio MCP server. Blocks until the client disconnects."""
    serve_stdio()

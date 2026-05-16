"""Thin wrapper around the official MCP Python SDK.

Supports two transports:
- streamable HTTP (remote MCP servers like Atlassian Rovo, GitHub hosted MCP)
- stdio (local MCP servers like the GitHub MCP container)

Each call opens + tears down a session. That's simple and safe for an MVP;
optimize later with a session pool if needed.
"""
from __future__ import annotations

import shlex
from contextlib import asynccontextmanager
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
except Exception:  # pragma: no cover - SDK not installed
    ClientSession = None  # type: ignore[assignment]


class McpClient:
    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        stdio_command: str | None = None,
    ):
        self.url = url
        self.token = token
        self.stdio_command = stdio_command
        if not (url or stdio_command):
            raise ValueError("McpClient requires either url or stdio_command")
        if ClientSession is None:
            raise RuntimeError("mcp SDK not installed; pip install mcp")

    @asynccontextmanager
    async def _session(self):
        if self.stdio_command:
            parts = shlex.split(self.stdio_command)
            params = StdioServerParameters(command=parts[0], args=parts[1:])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
            async with streamablehttp_client(self.url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

    async def list_tools(self) -> list[str]:
        async with self._session() as s:
            res = await s.list_tools()
            return [t.name for t in res.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        async with self._session() as s:
            res = await s.call_tool(name, arguments or {})
            # Concatenate text content for the caller; structured callers can re-parse.
            text_parts: list[str] = []
            for c in res.content or []:
                text = getattr(c, "text", None)
                if text:
                    text_parts.append(text)
            return {
                "text": "\n".join(text_parts),
                "structured": getattr(res, "structuredContent", None),
                "isError": getattr(res, "isError", False),
            }

"""Confluence MCP Provider.
Phase 2: Will connect to Atlassian Rovo MCP Server for Confluence access.
"""
from typing import Optional
from app.providers.base import DocsProvider


class ConfluenceMcpProvider(DocsProvider):
    """Confluence provider using Atlassian Rovo MCP Server.

    Not yet implemented. Set PROVIDER_MODE=mock to use mock data.

    Phase 2 implementation will:
    - Connect via HTTP SSE to Atlassian Rovo MCP endpoint
    - Authenticate with OAuth 2.1
    - Search and read pages, specs, release notes (read-only)
    """

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.api_token = api_token

    async def search_docs(self, query: str, space: Optional[str] = None) -> list[dict]:
        raise NotImplementedError(
            "Confluence MCP integration not yet implemented. "
            "Set PROVIDER_MODE=mock in .env to use mock data."
        )

    async def get_doc(self, doc_id: str) -> dict:
        raise NotImplementedError("Confluence MCP integration not yet implemented.")

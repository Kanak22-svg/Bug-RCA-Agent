"""Jira MCP Provider.
Phase 2: Will connect to Atlassian Rovo MCP Server for Jira access.
"""
from typing import Optional
from app.providers.base import IssueProvider


class JiraMcpProvider(IssueProvider):
    """Jira provider using Atlassian Rovo MCP Server.

    Not yet implemented. Set PROVIDER_MODE=mock to use mock data.

    Phase 2 implementation will:
    - Connect via HTTP SSE to Atlassian Rovo MCP endpoint
    - Authenticate with OAuth 2.1
    - Read issues, comments, linked tickets (read-only)
    """

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url
        self.api_token = api_token

    async def get_issue(self, issue_key: str) -> dict:
        raise NotImplementedError(
            "Jira MCP integration not yet implemented. "
            "Set PROVIDER_MODE=mock in .env to use mock data."
        )

    async def get_issue_comments(self, issue_key: str) -> list[dict]:
        raise NotImplementedError("Jira MCP integration not yet implemented.")

    async def get_related_issues(self, issue_key: str) -> list[dict]:
        raise NotImplementedError("Jira MCP integration not yet implemented.")

    async def search_issues(self, query: str, project: Optional[str] = None) -> list[dict]:
        raise NotImplementedError("Jira MCP integration not yet implemented.")

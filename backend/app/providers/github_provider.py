"""GitHub MCP Provider.
Phase 2: Will connect to GitHub MCP Server for repository access.
"""
from typing import Optional
from app.providers.base import CodeProvider


class GitHubMcpProvider(CodeProvider):
    """GitHub provider using GitHub MCP Server.

    Not yet implemented. Set PROVIDER_MODE=mock to use mock data.

    Phase 2 implementation will:
    - Connect via HTTP SSE to GitHub MCP Server
    - Authenticate with Personal Access Token (PAT)
    - Browse repos, files, commits, PRs, blame (read-only)
    """

    def __init__(self, token: str):
        self.token = token

    async def search_code(self, query: str, repo: str) -> list[dict]:
        raise NotImplementedError(
            "GitHub MCP integration not yet implemented. "
            "Set PROVIDER_MODE=mock in .env to use mock data."
        )

    async def get_file(self, repo: str, path: str) -> dict:
        raise NotImplementedError("GitHub MCP integration not yet implemented.")

    async def get_recent_commits(self, repo: str, path: Optional[str] = None, days: int = 30) -> list[dict]:
        raise NotImplementedError("GitHub MCP integration not yet implemented.")

    async def get_pull_request(self, repo: str, pr_number: int) -> dict:
        raise NotImplementedError("GitHub MCP integration not yet implemented.")

    async def get_blame(self, repo: str, path: str) -> list[dict]:
        raise NotImplementedError("GitHub MCP integration not yet implemented.")

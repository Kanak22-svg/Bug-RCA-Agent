"""Provider factory — wires concrete providers based on settings."""
from __future__ import annotations

from .atlassian_mcp import AtlassianMcpProvider
from .base import CodeProvider, DocsProvider, IssueProvider
from .github_mcp import GitHubMcpProvider
from .mcp_client import McpClient
from .mock_provider import MockCodeProvider, MockDocsProvider, MockIssueProvider
from ..config import get_settings


def build_providers() -> tuple[IssueProvider, DocsProvider, CodeProvider]:
    s = get_settings()

    # Atlassian (Jira + Confluence) shares one MCP client.
    atl_client: McpClient | None = None
    if s.issue_provider == "mcp" or s.docs_provider == "mcp":
        atl_client = McpClient(url=s.atlassian_mcp_url, token=s.atlassian_mcp_token)

    if s.issue_provider == "mcp":
        assert atl_client is not None
        issue: IssueProvider = AtlassianMcpProvider(atl_client)
    else:
        issue = MockIssueProvider()

    if s.docs_provider == "mcp":
        assert atl_client is not None
        docs: DocsProvider = AtlassianMcpProvider(atl_client)
    else:
        docs = MockDocsProvider()

    if s.code_provider == "mcp":
        gh_client = McpClient(
            url=s.github_mcp_url if not s.github_mcp_stdio else None,
            token=s.github_mcp_token if not s.github_mcp_stdio else None,
            stdio_command=s.github_mcp_command if s.github_mcp_stdio else None,
        )
        code: CodeProvider = GitHubMcpProvider(gh_client)
    else:
        code = MockCodeProvider()

    return issue, docs, code

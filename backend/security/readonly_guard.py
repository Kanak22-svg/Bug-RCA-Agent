"""Whitelist of read-only MCP tool names per server.

The orchestrator MUST go through `assert_readonly` before any tool call so we
can never accidentally invoke a write tool (create branch, comment, transition,
edit page, etc.). Update these lists as the upstream MCP servers evolve.
"""
from __future__ import annotations

# Atlassian Rovo MCP — Jira + Confluence read tools.
ATLASSIAN_READONLY: set[str] = {
    # Jira
    "getJiraIssue",
    "getJiraIssueRemoteIssueLinks",
    "searchJiraIssuesUsingJql",
    "getTransitionsForJiraIssue",  # read-only metadata
    "lookupJiraAccountId",
    "getVisibleJiraProjects",
    # Confluence
    "getConfluencePage",
    "searchConfluenceUsingCql",
    "getPagesInConfluenceSpace",
    "getConfluenceSpaces",
}

# GitHub MCP — read-only tools.
GITHUB_READONLY: set[str] = {
    "search_code",
    "search_repositories",
    "search_issues",
    "search_pull_requests",
    "get_file_contents",
    "list_commits",
    "get_commit",
    "list_pull_requests",
    "get_pull_request",
    "get_pull_request_files",
    "list_branches",
    "get_issue",
    "list_issue_comments",
    "list_releases",
    "get_repository",
}


def assert_readonly(server: str, tool: str) -> None:
    table = {"atlassian": ATLASSIAN_READONLY, "github": GITHUB_READONLY}.get(server)
    if table is None:
        raise PermissionError(f"Unknown MCP server: {server}")
    if tool not in table:
        raise PermissionError(
            f"Tool '{tool}' on '{server}' is not on the read-only whitelist; refusing to call."
        )

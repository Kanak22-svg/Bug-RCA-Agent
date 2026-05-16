"""GitHub MCP adapter — implements CodeProvider. Read-only tools only."""
from __future__ import annotations

import json
from typing import Any

from .base import CodeProvider
from .mcp_client import McpClient
from ..schemas import CodeHit, CommitInfo, PullRequest
from ..security.readonly_guard import assert_readonly


def _payload(result: dict[str, Any]) -> Any:
    if result.get("structured"):
        return result["structured"]
    text = result.get("text") or ""
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text}


def _split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        return repo, ""
    o, n = repo.split("/", 1)
    return o, n


class GitHubMcpProvider(CodeProvider):
    def __init__(self, client: McpClient):
        self.client = client

    async def _call(self, tool: str, args: dict[str, Any]) -> Any:
        assert_readonly("github", tool)
        return _payload(await self.client.call_tool(tool, args))

    async def search_code(self, query: str, repos: list[str], limit: int = 10) -> list[CodeHit]:
        scope = " ".join(f"repo:{r}" for r in repos) if repos else ""
        q = f"{query} {scope}".strip()
        data = await self._call("search_code", {"query": q, "perPage": limit})
        items = data.get("items", []) if isinstance(data, dict) else []
        out: list[CodeHit] = []
        for it in items[:limit]:
            repo = ((it.get("repository") or {}).get("full_name")) or ""
            out.append(CodeHit(
                repo=repo,
                path=it.get("path", ""),
                snippet=(it.get("text_matches") or [{}])[0].get("fragment", "") if it.get("text_matches") else "",
                score=float(it.get("score", 0.0)),
            ))
        return out

    async def get_file(self, repo: str, path: str) -> str | None:
        owner, name = _split_repo(repo)
        data = await self._call("get_file_contents", {"owner": owner, "repo": name, "path": path})
        if isinstance(data, dict):
            content = data.get("content") or data.get("text") or ""
            return content if isinstance(content, str) else json.dumps(content)
        return None

    async def recent_commits(self, repo: str, path: str | None = None, limit: int = 20) -> list[CommitInfo]:
        owner, name = _split_repo(repo)
        args: dict[str, Any] = {"owner": owner, "repo": name, "perPage": limit}
        if path:
            args["path"] = path
        data = await self._call("list_commits", args)
        items = data if isinstance(data, list) else (data.get("commits") if isinstance(data, dict) else []) or []
        out: list[CommitInfo] = []
        for c in items[:limit]:
            commit = c.get("commit", {}) if isinstance(c, dict) else {}
            files = [f.get("filename", "") for f in (c.get("files") or []) if isinstance(f, dict)]
            out.append(CommitInfo(
                sha=c.get("sha", ""),
                message=commit.get("message", ""),
                author=(commit.get("author") or {}).get("email", "") or (commit.get("author") or {}).get("name", ""),
                date=(commit.get("author") or {}).get("date", ""),
                files=files,
            ))
        return out

    async def get_pull_request(self, repo: str, number: int) -> PullRequest | None:
        owner, name = _split_repo(repo)
        data = await self._call("get_pull_request", {"owner": owner, "repo": name, "pullNumber": number})
        if not isinstance(data, dict) or not data:
            return None
        files_data = await self._call("get_pull_request_files", {"owner": owner, "repo": name, "pullNumber": number})
        files = [f.get("filename", "") for f in (files_data if isinstance(files_data, list) else []) if isinstance(f, dict)]
        return PullRequest(
            number=int(data.get("number", number)),
            title=data.get("title", ""),
            body=data.get("body", "") or "",
            author=(data.get("user") or {}).get("login", ""),
            merged_at=data.get("merged_at"),
            files=files,
            url=data.get("html_url", ""),
        )

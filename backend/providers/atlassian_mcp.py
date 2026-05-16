"""Atlassian Rovo MCP adapter — implements IssueProvider + DocsProvider.

All tool calls go through the read-only guard. Responses from the Rovo MCP
server are returned as MCP content blocks; we parse the structured/text payload
into our internal schemas defensively (the upstream schema may evolve).
"""
from __future__ import annotations

import json
from typing import Any

from .base import DocsProvider, IssueProvider
from .mcp_client import McpClient
from ..schemas import ConfluenceDoc, JiraComment, JiraIssue
from ..security.readonly_guard import assert_readonly


def _payload(result: dict[str, Any]) -> Any:
    if result.get("structured"):
        return result["structured"]
    text = result.get("text") or ""
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text}


class AtlassianMcpProvider(IssueProvider, DocsProvider):
    def __init__(self, client: McpClient):
        self.client = client

    async def _call(self, tool: str, args: dict[str, Any]) -> Any:
        assert_readonly("atlassian", tool)
        return _payload(await self.client.call_tool(tool, args))

    # ---------- IssueProvider ----------

    async def get_issue(self, issue_key: str) -> JiraIssue:
        data = await self._call("getJiraIssue", {"issueIdOrKey": issue_key})
        fields = data.get("fields", {}) if isinstance(data, dict) else {}

        def cf(name: str, default: str = "") -> str:
            # custom fields commonly land under unique IDs; tolerate both names + ids
            v = fields.get(name)
            if isinstance(v, dict):
                return v.get("value") or v.get("name") or default
            return v or default

        comments_raw = (fields.get("comment") or {}).get("comments", []) if isinstance(fields, dict) else []
        comments = [
            JiraComment(
                author=(c.get("author") or {}).get("displayName", ""),
                body=c.get("body", "") if isinstance(c.get("body"), str) else json.dumps(c.get("body", "")),
                created=c.get("created", ""),
            )
            for c in comments_raw
        ]
        linked = [
            (lk.get("outwardIssue") or lk.get("inwardIssue") or {}).get("key", "")
            for lk in fields.get("issuelinks", []) or []
        ]

        return JiraIssue(
            key=data.get("key", issue_key),
            title=fields.get("summary", ""),
            description=fields.get("description", "") if isinstance(fields.get("description"), str) else "",
            expected_behavior=cf("Expected Behavior"),
            actual_behavior=cf("Actual Behavior"),
            repro_status=(cf("Repro Status", "uncertain") or "uncertain").lower().replace(" ", "_"),  # type: ignore[arg-type]
            repro_steps=[s for s in (cf("Exact Steps Used") or "").splitlines() if s.strip()],
            environment=fields.get("environment") if isinstance(fields.get("environment"), dict) else {"raw": fields.get("environment", "")},
            failing_step=int(cf("Failing Step")) if (cf("Failing Step") or "").isdigit() else None,
            repro_notes=cf("Repro Notes"),
            priority=(fields.get("priority") or {}).get("name", ""),
            labels=fields.get("labels", []) or [],
            components=[c.get("name", "") for c in fields.get("components", []) or []],
            assignee=(fields.get("assignee") or {}).get("displayName", ""),
            reporter=(fields.get("reporter") or {}).get("displayName", ""),
            epic=cf("Epic Link"),
            linked_issue_keys=[k for k in linked if k],
            comments=comments,
            url=data.get("self", ""),
        )

    async def get_related_issues(self, issue: JiraIssue, limit: int = 10) -> list[JiraIssue]:
        clauses: list[str] = []
        if issue.linked_issue_keys:
            clauses.append("key in (" + ",".join(issue.linked_issue_keys) + ")")
        if issue.components:
            clauses.append("component in (" + ",".join(f'"{c}"' for c in issue.components) + ")")
        if issue.labels:
            clauses.append("labels in (" + ",".join(f'"{l}"' for l in issue.labels) + ")")
        if not clauses:
            return []
        jql = " OR ".join(clauses) + f' AND key != "{issue.key}" ORDER BY updated DESC'
        data = await self._call("searchJiraIssuesUsingJql", {"jql": jql, "limit": limit})
        out: list[JiraIssue] = []
        for it in (data.get("issues") if isinstance(data, dict) else []) or []:
            f = it.get("fields", {})
            out.append(JiraIssue(
                key=it.get("key", ""),
                title=f.get("summary", ""),
                description=f.get("description", "") if isinstance(f.get("description"), str) else "",
                labels=f.get("labels", []) or [],
                components=[c.get("name", "") for c in f.get("components", []) or []],
            ))
        return out

    # ---------- DocsProvider ----------

    async def search_docs(self, query: str, limit: int = 5) -> list[ConfluenceDoc]:
        cql = f'text ~ "{query}" AND type = "page"'
        data = await self._call("searchConfluenceUsingCql", {"cql": cql, "limit": limit})
        out: list[ConfluenceDoc] = []
        for r in (data.get("results") if isinstance(data, dict) else []) or []:
            out.append(ConfluenceDoc(
                id=str(r.get("id", "")),
                title=r.get("title", ""),
                url=(r.get("_links") or {}).get("webui", ""),
                snippet=r.get("excerpt", "") or "",
                space=(r.get("space") or {}).get("key", ""),
            ))
        return out

    async def get_doc(self, doc_id: str) -> ConfluenceDoc | None:
        data = await self._call("getConfluencePage", {"pageId": doc_id})
        if not isinstance(data, dict) or not data:
            return None
        body = ""
        b = data.get("body") or {}
        if isinstance(b, dict):
            body = (b.get("storage") or {}).get("value", "") or (b.get("view") or {}).get("value", "")
        return ConfluenceDoc(
            id=str(data.get("id", doc_id)),
            title=data.get("title", ""),
            url=(data.get("_links") or {}).get("webui", ""),
            snippet=body[:240],
            body=body,
            space=(data.get("space") or {}).get("key", ""),
        )

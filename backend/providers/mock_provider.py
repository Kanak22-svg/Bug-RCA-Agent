"""Mock provider — lets you run the full pipeline locally with no credentials.

It returns plausible Jira / Confluence / GitHub data for the demo issue
``DEMO-1`` (an "Export button disabled for admin" bug) so the UI shows real
output end-to-end. Any other issue key returns a generic skeleton.
"""
from __future__ import annotations

from .base import CodeProvider, DocsProvider, IssueProvider
from ..schemas import CodeHit, CommitInfo, ConfluenceDoc, JiraComment, JiraIssue, PullRequest


_DEMO_ISSUE = JiraIssue(
    key="DEMO-1",
    title="Export button disabled for admin",
    description="Admins report that the Export button on the Reports page is disabled in staging.",
    expected_behavior="Admin should be able to export reports from the Reports page.",
    actual_behavior="Export button is rendered but disabled for users with the admin role.",
    repro_status="reproduced",
    repro_steps=[
        "Login as admin",
        "Navigate to /reports",
        "Select any report",
        "Observe that the Export button is disabled",
    ],
    environment={"env": "staging", "browser": "Chrome 124", "build": "v2.3.1"},
    failing_step=4,
    repro_notes="Happens only for admin role on staging. Not reproducible in dev.",
    priority="High",
    severity="S2",
    labels=["bug", "reports-ui", "regression-suspect"],
    components=["reports", "permissions"],
    assignee="alice@example.com",
    reporter="bob@example.com",
    team="reports-platform",
    epic="REPORTS-100",
    linked_issue_keys=["DEMO-2"],
    comments=[
        JiraComment(author="alice", body="Reproduced on staging build v2.3.1.", created="2026-05-01"),
        JiraComment(author="carol", body="Worked last week — looks like a regression.", created="2026-05-02"),
    ],
    url="https://example.atlassian.net/browse/DEMO-1",
)

_RELATED = [
    JiraIssue(
        key="DEMO-2",
        title="Permissions cache invalidation flaky after role change",
        description="Roles do not refresh until logout in some tenants.",
        labels=["permissions"],
        components=["permissions"],
        url="https://example.atlassian.net/browse/DEMO-2",
    )
]

_DOCS = [
    ConfluenceDoc(
        id="conf-101",
        title="Reports — Export feature spec",
        url="https://example.atlassian.net/wiki/spaces/RPT/pages/101",
        snippet="Export is available to all roles with reports:read permission, including admin.",
        body=(
            "Export is available to all roles that hold the reports:read permission. "
            "Admin role inherits reports:read by default. "
            "There is no documented restriction on admin export."
        ),
        space="RPT",
    ),
    ConfluenceDoc(
        id="conf-102",
        title="v2.3 release notes",
        url="https://example.atlassian.net/wiki/spaces/RPT/pages/102",
        snippet="Refactored permissions resolution in CanExport.",
        body="v2.3 refactored permissions resolution to use the new RoleResolver. No behavior change intended.",
        space="RPT",
    ),
]

_CODE_HITS = [
    CodeHit(
        repo="acme/web-app",
        path="src/features/reports/ExportPanel.tsx",
        snippet="const enabled = isExportEnabled(user); return <Button disabled={!enabled}>Export</Button>;",
        score=0.91,
        symbol="isExportEnabled",
    ),
    CodeHit(
        repo="acme/permissions-service",
        path="pkg/roles/export.go",
        snippet="func CanExport(role Role) bool { return role.HasPermission(\"reports:read\") }",
        score=0.74,
        symbol="CanExport",
    ),
]

_COMMITS = [
    CommitInfo(
        sha="a1b2c3d",
        message="Refactor RoleResolver; tighten permission checks (#812)",
        author="dave@example.com",
        date="2026-04-28",
        files=["pkg/roles/export.go", "pkg/roles/resolver.go"],
        pr_number=812,
    ),
    CommitInfo(
        sha="e4f5a6b",
        message="Reports UI: memoize export button state",
        author="eve@example.com",
        date="2026-04-20",
        files=["src/features/reports/ExportPanel.tsx"],
        pr_number=805,
    ),
]

_PR_812 = PullRequest(
    number=812,
    title="Refactor RoleResolver; tighten permission checks",
    body=(
        "Refactors RoleResolver. Should be behavior-preserving. "
        "Note: removed legacy admin-bypass branch — all callers should already grant reports:read to admin."
    ),
    author="dave@example.com",
    merged_at="2026-04-28",
    files=["pkg/roles/export.go", "pkg/roles/resolver.go"],
    url="https://github.com/acme/permissions-service/pull/812",
)


class MockIssueProvider(IssueProvider):
    async def get_issue(self, issue_key: str) -> JiraIssue:
        if issue_key == "DEMO-1":
            return _DEMO_ISSUE
        return JiraIssue(key=issue_key, title=f"(mock) {issue_key}", description="Mock issue.")

    async def get_related_issues(self, issue: JiraIssue, limit: int = 10) -> list[JiraIssue]:
        if issue.key == "DEMO-1":
            return _RELATED[:limit]
        return []


class MockDocsProvider(DocsProvider):
    async def search_docs(self, query: str, limit: int = 5) -> list[ConfluenceDoc]:
        q = query.lower()
        hits = [d for d in _DOCS if any(t in (d.title + d.body).lower() for t in q.split())]
        return (hits or _DOCS)[:limit]

    async def get_doc(self, doc_id: str) -> ConfluenceDoc | None:
        return next((d for d in _DOCS if d.id == doc_id), None)


class MockCodeProvider(CodeProvider):
    async def search_code(self, query: str, repos: list[str], limit: int = 10) -> list[CodeHit]:
        q = query.lower()
        hits = [h for h in _CODE_HITS if any(t in (h.path + h.snippet).lower() for t in q.split())]
        return (hits or _CODE_HITS)[:limit]

    async def get_file(self, repo: str, path: str) -> str | None:
        for h in _CODE_HITS:
            if h.repo == repo and h.path == path:
                return h.snippet
        return None

    async def recent_commits(self, repo: str, path: str | None = None, limit: int = 20) -> list[CommitInfo]:
        out = [c for c in _COMMITS if not path or path in c.files]
        return out[:limit]

    async def get_pull_request(self, repo: str, number: int) -> PullRequest | None:
        if number == 812:
            return _PR_812
        return None

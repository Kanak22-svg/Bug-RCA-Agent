from typing import Optional
from datetime import datetime, timezone, timedelta
from app.providers.base import IssueProvider, DocsProvider, CodeProvider


class MockIssueProvider(IssueProvider):
    """Mock Jira provider with hardcoded realistic data."""

    ISSUES = {
        "PROJ-1234": {
            "key": "PROJ-1234",
            "title": "Export button disabled for admin users",
            "description": "When logged in as an admin user on the reports page, the 'Export' button is grayed out and not clickable. This was working last week. The button works fine for owner-role users.",
            "expected_behavior": "Admin users should be able to export reports, as they have been able to do since the feature was launched.",
            "actual_behavior": "The Export button is disabled (grayed out) for admin users. Clicking it does nothing. No error message is shown.",
            "environment": {
                "env": "staging",
                "browser": "Chrome 125",
                "os": "macOS",
                "build": "v2.3.1",
                "deploy_date": "2026-05-24"
            },
            "priority": "High",
            "severity": "Major",
            "status": "Open",
            "component": "Reports",
            "labels": ["bug", "reports-ui", "permissions", "regression-candidate"],
            "assignee": "jane.smith",
            "assigned_team": "Platform UI",
            "reporter": "john.doe",
            "created_at": "2026-05-26T10:30:00Z",
            "updated_at": "2026-05-28T14:15:00Z",
            "linked_issues": ["PROJ-1100", "PROJ-1220", "PROJ-1245"],
            "attachments": [
                {"filename": "export-btn-disabled.png", "size": 245000, "type": "image/png"}
            ],
            "comments": [
                {
                    "author": "john.doe",
                    "body": "I've confirmed this is happening in staging. Tested with three different admin accounts.",
                    "created_at": "2026-05-26T11:00:00Z"
                },
                {
                    "author": "jane.smith",
                    "body": "I can reproduce this. It seems to have started after the last deployment on May 24. Checking the recent changes now.",
                    "created_at": "2026-05-27T09:30:00Z"
                },
                {
                    "author": "mike.wilson",
                    "body": "This might be related to PR #342 that changed permission checks for the export feature. We were only supposed to restrict viewers, not admins.",
                    "created_at": "2026-05-28T14:15:00Z"
                }
            ]
        },
        "PROJ-1100": {
            "key": "PROJ-1100",
            "title": "Add export feature for reports",
            "description": "Implement the ability to export reports in CSV and PDF formats. All authenticated users with role 'admin' or 'owner' should be able to export.",
            "status": "Done",
            "priority": "High",
            "component": "Reports",
            "labels": ["feature", "reports-ui"],
            "assignee": "alex.chen",
            "reporter": "product.manager",
            "created_at": "2026-02-15T10:00:00Z",
            "relation_type": "parent_feature",
            "relation_reason": "Original story that implemented the export feature for admin+owner roles"
        },
        "PROJ-1220": {
            "key": "PROJ-1220",
            "title": "Restrict export access for viewer role",
            "description": "Viewers should not have access to export reports. Only admin and owner roles should be able to export. This was requested by the security team.",
            "status": "Done",
            "priority": "Medium",
            "component": "Reports",
            "labels": ["enhancement", "permissions", "security"],
            "assignee": "dev.name",
            "reporter": "security.lead",
            "created_at": "2026-05-18T09:00:00Z",
            "relation_type": "linked_implements",
            "relation_reason": "This story led to PR #342 which likely caused the bug by being overly restrictive"
        },
        "PROJ-1050": {
            "key": "PROJ-1050",
            "title": "Reports page loads slowly for large datasets",
            "description": "When there are more than 1000 reports, the page takes over 10 seconds to load.",
            "status": "Closed",
            "priority": "Medium",
            "component": "Reports",
            "labels": ["bug", "performance", "reports-ui"],
            "assignee": "alex.chen",
            "reporter": "qa.engineer",
            "created_at": "2026-01-20T08:00:00Z",
            "relation_type": "same_component",
            "relation_reason": "Different issue but same Reports module — low relevance"
        },
        "PROJ-1245": {
            "key": "PROJ-1245",
            "title": "Admin cannot download PDF report",
            "description": "Admin users are unable to download reports in PDF format. The download button does nothing.",
            "status": "Open",
            "priority": "High",
            "component": "Reports",
            "labels": ["bug", "reports-ui", "permissions"],
            "assignee": "jane.smith",
            "reporter": "support.team",
            "created_at": "2026-05-27T16:00:00Z",
            "relation_type": "possibly_duplicate",
            "relation_reason": "May be the same root cause — admin export/download permissions broken after same deployment"
        }
    }

    async def get_issue(self, issue_key: str) -> dict:
        if issue_key in self.ISSUES:
            return self.ISSUES[issue_key]
        return {
            "key": issue_key,
            "title": f"Mock issue {issue_key}",
            "description": "This is a mock issue for testing.",
            "status": "Open",
            "priority": "Medium",
            "component": "Unknown",
            "labels": ["bug"],
            "assignee": "unassigned",
            "reporter": "unknown",
        }

    async def get_issue_comments(self, issue_key: str) -> list[dict]:
        issue = self.ISSUES.get(issue_key, {})
        return issue.get("comments", [])

    async def get_related_issues(self, issue_key: str) -> list[dict]:
        issue = self.ISSUES.get(issue_key, {})
        linked_keys = issue.get("linked_issues", [])
        related = []
        for key in linked_keys:
            if key in self.ISSUES:
                related.append(self.ISSUES[key])
        # Also find issues with same component
        component = issue.get("component")
        if component:
            for k, v in self.ISSUES.items():
                if k != issue_key and k not in linked_keys and v.get("component") == component:
                    v_copy = dict(v)
                    v_copy["relation_type"] = "same_component"
                    v_copy["relation_reason"] = f"Same component: {component}"
                    related.append(v_copy)
        return related

    async def search_issues(self, query: str, project: Optional[str] = None) -> list[dict]:
        results = []
        query_lower = query.lower()
        for issue in self.ISSUES.values():
            text = f"{issue.get('title', '')} {issue.get('description', '')}".lower()
            if query_lower in text:
                results.append(issue)
        return results


class MockDocsProvider(DocsProvider):
    """Mock Confluence provider with hardcoded realistic data."""

    DOCS = {
        "DOC-001": {
            "id": "DOC-001",
            "title": "Reports Export Feature Spec",
            "space": "Product Specs",
            "url": "https://mycompany.atlassian.net/wiki/spaces/SPECS/pages/001/Reports+Export+Feature+Spec",
            "last_updated": "2026-03-15T10:00:00Z",
            "author": "product.manager",
            "content": """# Reports Export Feature Specification

## Overview
The reports export feature allows users to export report data in CSV and PDF formats.

## Access Control
All authenticated users with role 'admin' or 'owner' should be able to export reports.
Viewer-role users should NOT have export access (added in v2.3).

## Supported Formats
- CSV: Raw data export
- PDF: Formatted report with charts

## User Flow
1. User navigates to Reports page
2. User selects a report
3. User clicks 'Export' button in toolbar
4. User selects format (CSV/PDF)
5. Download begins automatically

## History
- v2.0: Initial export feature (admin + owner)
- v2.3: Restricted viewer access per security request
""",
            "key_excerpt": "All authenticated users with role 'admin' or 'owner' should be able to export reports.",
            "relevance_tag": "CONTRADICTS"
        },
        "DOC-002": {
            "id": "DOC-002",
            "title": "Permission Model v2 Design Doc",
            "space": "Engineering",
            "url": "https://mycompany.atlassian.net/wiki/spaces/ENG/pages/002/Permission+Model+v2",
            "last_updated": "2026-04-02T14:00:00Z",
            "author": "tech.lead",
            "content": """# Permission Model v2

## Changes from v1
- Introduce granular role-based access control
- Viewer role should not have export, delete, or admin panel access
- Admin role retains all current permissions
- Owner role retains all current permissions

## Export Permissions
- Owner: full export access
- Admin: full export access
- Editor: export own reports only
- Viewer: NO export access

## Implementation Notes
The isExportEnabled() function in ExportPanel.tsx should check user.role against the allowed roles array.
Allowed roles for export: ['owner', 'admin', 'editor_own']
""",
            "key_excerpt": "Viewer role should not have export access. Admin role retains all current permissions.",
            "relevance_tag": "SUPPORTS"
        },
        "DOC-003": {
            "id": "DOC-003",
            "title": "v2.3.1 Release Notes",
            "space": "Engineering",
            "url": "https://mycompany.atlassian.net/wiki/spaces/ENG/pages/003/v2.3.1+Release+Notes",
            "last_updated": "2026-05-24T16:00:00Z",
            "author": "release.manager",
            "content": """# v2.3.1 Release Notes (May 24, 2026)

## Changes
- PROJ-1220: Restricted export access for viewer role
- PROJ-1210: Fixed pagination on reports list
- PROJ-1215: Updated chart rendering library

## Known Issues
None reported at time of release.

## Deployment
Deployed to staging: May 24 10:00 UTC
Deployed to production: May 24 14:00 UTC
""",
            "key_excerpt": "PROJ-1220: Restricted export access for viewer role. Deployed May 24.",
            "relevance_tag": "RELATED"
        }
    }

    async def search_docs(self, query: str, space: Optional[str] = None) -> list[dict]:
        results = []
        query_lower = query.lower()
        for doc in self.DOCS.values():
            text = f"{doc['title']} {doc['content']}".lower()
            if query_lower in text or any(kw in text for kw in query_lower.split()):
                result = {k: v for k, v in doc.items() if k != "content"}
                result["content_summary"] = doc["content"][:300] + "..."
                results.append(result)
        return results

    async def get_doc(self, doc_id: str) -> dict:
        if doc_id in self.DOCS:
            return self.DOCS[doc_id]
        return {"id": doc_id, "title": "Unknown Document", "content": ""}


class MockCodeProvider(CodeProvider):
    """Mock GitHub provider with hardcoded realistic data."""

    FILES = {
        "web-app:src/features/reports/ExportPanel.tsx": {
            "repo": "web-app",
            "path": "src/features/reports/ExportPanel.tsx",
            "content": """import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { exportReport } from '@/services/reportService';

interface ExportPanelProps {
  reportId: string;
  format: 'csv' | 'pdf';
}

function isExportEnabled(user: { role: string }): boolean {
  // Updated in PR #342 to restrict viewer access
  // BUG: This only allows 'owner', but should also allow 'admin'
  return user.role === 'owner';
}

export function ExportPanel({ reportId, format }: ExportPanelProps) {
  const { user } = useAuth();
  const canExport = isExportEnabled(user);

  const handleExport = async () => {
    if (!canExport) return;
    await exportReport(reportId, format);
  };

  return (
    <div className="export-panel">
      <Button
        onClick={handleExport}
        disabled={!canExport}
        variant={canExport ? 'primary' : 'disabled'}
      >
        Export {format.toUpperCase()}
      </Button>
    </div>
  );
}""",
            "language": "typescript",
            "last_modified": "2026-05-24T09:30:00Z",
            "last_commit_sha": "abc123f"
        },
        "web-app:src/utils/permissions.ts": {
            "repo": "web-app",
            "path": "src/utils/permissions.ts",
            "content": """export type Role = 'owner' | 'admin' | 'editor' | 'viewer';

export interface Permission {
  canExport: boolean;
  canDelete: boolean;
  canAdmin: boolean;
}

export function getPermissions(role: Role): Permission {
  switch (role) {
    case 'owner':
      return { canExport: true, canDelete: true, canAdmin: true };
    case 'admin':
      return { canExport: true, canDelete: false, canAdmin: true };
    case 'editor':
      return { canExport: false, canDelete: false, canAdmin: false };
    case 'viewer':
      return { canExport: false, canDelete: false, canAdmin: false };
  }
}""",
            "language": "typescript",
            "last_modified": "2026-04-10T12:00:00Z",
            "last_commit_sha": "ff8822a"
        },
        "permissions-service:pkg/roles/export.go": {
            "repo": "permissions-service",
            "path": "pkg/roles/export.go",
            "content": """package roles

// CanExport checks if a role is allowed to export reports.
// Allowed: owner, admin
// Denied: editor, viewer
func CanExport(role string) bool {
\tswitch role {
\tcase "owner", "admin":
\t\treturn true
\tdefault:
\t\treturn false
\t}
}""",
            "language": "go",
            "last_modified": "2026-03-20T08:00:00Z",
            "last_commit_sha": "991abc2"
        }
    }

    COMMITS = [
        {
            "sha": "abc123f",
            "repo": "web-app",
            "message": "restrict export to owner role only\n\nPart of PROJ-1220: restrict viewer access to export",
            "author": "dev.name",
            "date": "2026-05-24T09:30:00Z",
            "files_changed": ["src/features/reports/ExportPanel.tsx"],
            "pr_number": 342
        },
        {
            "sha": "def456a",
            "repo": "web-app",
            "message": "add test for viewer export restriction",
            "author": "dev.name",
            "date": "2026-05-24T09:15:00Z",
            "files_changed": ["src/features/reports/__tests__/ExportPanel.test.tsx"],
            "pr_number": 342
        },
        {
            "sha": "789bcd0",
            "repo": "web-app",
            "message": "refactor permission utilities to use centralized config",
            "author": "other.dev",
            "date": "2026-05-22T14:00:00Z",
            "files_changed": ["src/utils/permissions.ts", "src/config/roles.ts"],
            "pr_number": 338
        },
        {
            "sha": "ff8822a",
            "repo": "web-app",
            "message": "update permissions util with editor role support",
            "author": "alex.chen",
            "date": "2026-04-10T12:00:00Z",
            "files_changed": ["src/utils/permissions.ts"],
            "pr_number": 310
        },
        {
            "sha": "112233c",
            "repo": "web-app",
            "message": "fix pagination on reports list page",
            "author": "alex.chen",
            "date": "2026-05-23T11:00:00Z",
            "files_changed": ["src/features/reports/ReportsList.tsx"],
            "pr_number": 340
        }
    ]

    PULL_REQUESTS = {
        342: {
            "number": 342,
            "repo": "web-app",
            "title": "Restrict export to privileged roles",
            "description": "Implements PROJ-1220. Restricts the export feature so that only privileged roles (owner) can access it. Viewers should no longer see the export button enabled.\n\nChanges:\n- Updated isExportEnabled() to check for owner role\n- Added test for viewer restriction\n\nTesting:\n- Verified viewer cannot export\n- Verified owner can still export",
            "author": "dev.name",
            "state": "merged",
            "merged_at": "2026-05-24T09:45:00Z",
            "created_at": "2026-05-23T16:00:00Z",
            "base_branch": "main",
            "commits": ["def456a", "abc123f"],
            "files_changed": [
                "src/features/reports/ExportPanel.tsx",
                "src/features/reports/__tests__/ExportPanel.test.tsx"
            ],
            "review_comments": [
                {
                    "author": "reviewer.one",
                    "body": "Looks good. Viewer restriction works as expected.",
                    "created_at": "2026-05-24T08:00:00Z"
                }
            ],
            "linked_issues": ["PROJ-1220"]
        },
        338: {
            "number": 338,
            "repo": "web-app",
            "title": "Refactor permission utilities",
            "description": "Refactored permission checking to use a centralized config instead of hardcoded role checks scattered across the codebase.",
            "author": "other.dev",
            "state": "merged",
            "merged_at": "2026-05-22T15:00:00Z",
            "created_at": "2026-05-21T10:00:00Z",
            "base_branch": "main",
            "commits": ["789bcd0"],
            "files_changed": [
                "src/utils/permissions.ts",
                "src/config/roles.ts"
            ],
            "linked_issues": []
        }
    }

    BLAME_DATA = {
        "web-app:src/features/reports/ExportPanel.tsx": [
            {"line": 1, "sha": "initial01", "author": "alex.chen", "date": "2026-02-20"},
            {"line": 12, "sha": "abc123f", "author": "dev.name", "date": "2026-05-24"},
            {"line": 13, "sha": "abc123f", "author": "dev.name", "date": "2026-05-24"},
            {"line": 14, "sha": "abc123f", "author": "dev.name", "date": "2026-05-24"},
            {"line": 15, "sha": "abc123f", "author": "dev.name", "date": "2026-05-24"},
        ]
    }

    async def search_code(self, query: str, repo: str) -> list[dict]:
        results = []
        query_lower = query.lower()
        for key, file_data in self.FILES.items():
            if repo and not key.startswith(repo + ":"):
                continue
            text = f"{file_data['path']} {file_data['content']}".lower()
            if query_lower in text or any(kw in text for kw in query_lower.split()):
                results.append({
                    "repo": file_data["repo"],
                    "path": file_data["path"],
                    "language": file_data.get("language"),
                    "last_modified": file_data.get("last_modified"),
                    "match_preview": file_data["content"][:200],
                })
        return results

    async def get_file(self, repo: str, path: str) -> dict:
        key = f"{repo}:{path}"
        if key in self.FILES:
            return self.FILES[key]
        return {"repo": repo, "path": path, "content": "// File not found in mock data", "language": "unknown"}

    async def get_recent_commits(self, repo: str, path: Optional[str] = None, days: int = 30) -> list[dict]:
        results = []
        for commit in self.COMMITS:
            if commit["repo"] != repo:
                continue
            if path and path not in commit.get("files_changed", []):
                continue
            results.append(commit)
        return sorted(results, key=lambda c: c["date"], reverse=True)

    async def get_pull_request(self, repo: str, pr_number: int) -> dict:
        if pr_number in self.PULL_REQUESTS:
            return self.PULL_REQUESTS[pr_number]
        return {"number": pr_number, "repo": repo, "title": "Unknown PR", "state": "unknown"}

    async def get_blame(self, repo: str, path: str) -> list[dict]:
        key = f"{repo}:{path}"
        return self.BLAME_DATA.get(key, [])

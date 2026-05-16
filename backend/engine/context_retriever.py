"""Pulls together docs/code/commits relevant to the bug into one context pack."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..providers.base import CodeProvider, DocsProvider, IssueProvider
from ..schemas import CodeHit, CommitInfo, ConfluenceDoc, JiraIssue, NormalizedBug


@dataclass
class ContextPack:
    issue: JiraIssue
    related_issues: list[JiraIssue] = field(default_factory=list)
    docs: list[ConfluenceDoc] = field(default_factory=list)
    code_hits: list[CodeHit] = field(default_factory=list)
    commits_by_file: dict[str, list[CommitInfo]] = field(default_factory=dict)


async def gather_context(
    *,
    bug: NormalizedBug,
    issue: JiraIssue,
    repos: list[str],
    issue_provider: IssueProvider,
    docs_provider: DocsProvider,
    code_provider: CodeProvider,
) -> ContextPack:
    pack = ContextPack(issue=issue)

    # Related Jira tickets (linked, same component, same labels) — provider decides.
    pack.related_issues = await issue_provider.get_related_issues(issue, limit=10)

    # Confluence: query by title + top keywords.
    queries = [issue.title] + bug.components + bug.labels
    seen: dict[str, ConfluenceDoc] = {}
    for q in queries[:4]:
        if not q:
            continue
        for d in await docs_provider.search_docs(q, limit=4):
            seen[d.id] = d
    pack.docs = list(seen.values())[:8]

    # GitHub: search code by keyword combinations.
    code_query = " ".join(bug.keywords[:6]) or issue.title
    pack.code_hits = await code_provider.search_code(code_query, repos=repos, limit=10)

    # Recent commits per top candidate file.
    for hit in pack.code_hits[:5]:
        try:
            commits = await code_provider.recent_commits(hit.repo, path=hit.path, limit=10)
        except Exception:
            commits = []
        pack.commits_by_file[f"{hit.repo}:{hit.path}"] = commits

    return pack

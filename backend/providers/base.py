"""Abstract provider interfaces. Business logic depends ONLY on these."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import CodeHit, CommitInfo, ConfluenceDoc, JiraIssue, PullRequest


class IssueProvider(ABC):
    """Read-only Jira access."""

    @abstractmethod
    async def get_issue(self, issue_key: str) -> JiraIssue: ...

    @abstractmethod
    async def get_related_issues(self, issue: JiraIssue, limit: int = 10) -> list[JiraIssue]: ...


class DocsProvider(ABC):
    """Read-only Confluence access."""

    @abstractmethod
    async def search_docs(self, query: str, limit: int = 5) -> list[ConfluenceDoc]: ...

    @abstractmethod
    async def get_doc(self, doc_id: str) -> ConfluenceDoc | None: ...


class CodeProvider(ABC):
    """Read-only GitHub access."""

    @abstractmethod
    async def search_code(self, query: str, repos: list[str], limit: int = 10) -> list[CodeHit]: ...

    @abstractmethod
    async def get_file(self, repo: str, path: str) -> str | None: ...

    @abstractmethod
    async def recent_commits(self, repo: str, path: str | None = None, limit: int = 20) -> list[CommitInfo]: ...

    @abstractmethod
    async def get_pull_request(self, repo: str, number: int) -> PullRequest | None: ...

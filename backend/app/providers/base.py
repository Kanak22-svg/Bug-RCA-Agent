from abc import ABC, abstractmethod
from typing import Optional


class IssueProvider(ABC):
    """Interface for fetching bug/issue data (Jira)."""

    @abstractmethod
    async def get_issue(self, issue_key: str) -> dict:
        """Fetch a single issue by key. Returns full issue data."""
        pass

    @abstractmethod
    async def get_issue_comments(self, issue_key: str) -> list[dict]:
        """Fetch comments on an issue."""
        pass

    @abstractmethod
    async def get_related_issues(self, issue_key: str) -> list[dict]:
        """Fetch issues related to the given issue (linked, same component, etc.)."""
        pass

    @abstractmethod
    async def search_issues(self, query: str, project: Optional[str] = None) -> list[dict]:
        """Search for issues matching a query."""
        pass


class DocsProvider(ABC):
    """Interface for fetching documentation (Confluence)."""

    @abstractmethod
    async def search_docs(self, query: str, space: Optional[str] = None) -> list[dict]:
        """Search documentation by query string."""
        pass

    @abstractmethod
    async def get_doc(self, doc_id: str) -> dict:
        """Fetch a single document by ID."""
        pass


class CodeProvider(ABC):
    """Interface for fetching code and repository data (GitHub)."""

    @abstractmethod
    async def search_code(self, query: str, repo: str) -> list[dict]:
        """Search for code matching query in a repository."""
        pass

    @abstractmethod
    async def get_file(self, repo: str, path: str) -> dict:
        """Get file contents from a repository."""
        pass

    @abstractmethod
    async def get_recent_commits(self, repo: str, path: Optional[str] = None, days: int = 30) -> list[dict]:
        """Get recent commits, optionally filtered by file path."""
        pass

    @abstractmethod
    async def get_pull_request(self, repo: str, pr_number: int) -> dict:
        """Get pull request details."""
        pass

    @abstractmethod
    async def get_blame(self, repo: str, path: str) -> list[dict]:
        """Get blame/annotation data for a file."""
        pass

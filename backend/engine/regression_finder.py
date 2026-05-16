"""Regression finder — rank suspicious commits / PRs."""
from __future__ import annotations

from ..providers.base import CodeProvider
from ..schemas import CodeCandidateOut, CommitCandidateOut
from .context_retriever import ContextPack


_RISKY_TOKENS = ("refactor", "permission", "auth", "role", "bypass", "remove", "delete", "rewrite", "migrate")


async def find_regressions(
    *,
    pack: ContextPack,
    candidates: list[CodeCandidateOut],
    code_provider: CodeProvider,
    top_n: int = 5,
) -> list[CommitCandidateOut]:
    out: list[CommitCandidateOut] = []
    seen: set[tuple[str, str]] = set()

    for cand in candidates:
        key = f"{cand.repo}:{cand.file_path}"
        commits = pack.commits_by_file.get(key, [])
        for c in commits[:6]:
            dedupe = (cand.repo, c.sha)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            risk = sum(1 for t in _RISKY_TOKENS if t in c.message.lower())
            confidence = min(0.95, 0.4 + 0.1 * risk + 0.2 * cand.confidence)
            rationale_parts = [f"Touches candidate file {cand.file_path}"]
            if risk:
                rationale_parts.append(f"Commit message mentions risky terms ({risk})")
            if c.pr_number:
                pr = await code_provider.get_pull_request(cand.repo, c.pr_number)
                if pr and pr.body:
                    rationale_parts.append(f"PR #{pr.number}: {pr.title}")
            out.append(CommitCandidateOut(
                repo=cand.repo,
                commit_sha=c.sha,
                pr_number=c.pr_number,
                confidence=round(confidence, 3),
                classification="suspect",
                rationale="; ".join(rationale_parts),
            ))

    out.sort(key=lambda x: x.confidence, reverse=True)
    return out[:top_n]

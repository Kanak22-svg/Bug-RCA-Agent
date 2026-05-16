"""Code localization — rank candidate files/functions for the bug."""
from __future__ import annotations

from ..schemas import CodeCandidateOut, NormalizedBug
from .context_retriever import ContextPack


def _score(hit_score: float, path: str, keywords: list[str]) -> tuple[float, str]:
    bonus = 0.0
    reasons: list[str] = []
    p = path.lower()
    for kw in keywords[:10]:
        if kw and kw in p:
            bonus += 0.05
            reasons.append(f"path matches '{kw}'")
    score = min(0.99, max(0.0, hit_score) * 0.6 + bonus + 0.3)
    return score, "; ".join(reasons) or "search-engine relevance"


def localize(bug: NormalizedBug, pack: ContextPack, top_n: int = 5) -> list[CodeCandidateOut]:
    candidates: list[CodeCandidateOut] = []
    for hit in pack.code_hits:
        confidence, rationale = _score(hit.score, hit.path, bug.keywords)
        candidates.append(CodeCandidateOut(
            repo=hit.repo,
            file_path=hit.path,
            symbol=hit.symbol or "",
            confidence=round(confidence, 3),
            rationale=rationale + (f"; snippet hint: {hit.snippet[:140]}" if hit.snippet else ""),
        ))
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:top_n]

"""Intent analyzer — likely intentional vs likely regression vs unclear.

Uses an LLM if configured; otherwise falls back to a transparent rule-based
heuristic over the assembled context pack.
"""
from __future__ import annotations

import json
from typing import Any

from ..llm.client import complete_json
from ..schemas import Classification, NormalizedBug
from .context_retriever import ContextPack


def _heuristic(bug: NormalizedBug, pack: ContextPack) -> dict[str, Any]:
    intentional_signals: list[str] = []
    regression_signals: list[str] = []

    actual_lower = bug.actual_behavior.lower()
    expected_lower = bug.expected_behavior.lower()

    for d in pack.docs:
        body = (d.body or d.snippet or "").lower()
        if expected_lower and any(tok in body for tok in expected_lower.split() if len(tok) > 4):
            regression_signals.append(f"Confluence '{d.title}' supports expected behavior")
        if actual_lower and any(tok in body for tok in actual_lower.split() if len(tok) > 4):
            intentional_signals.append(f"Confluence '{d.title}' describes current behavior")

    if (bug.manual_repro or {}).get("status") == "reproduced":
        regression_signals.append("Manual repro confirmed")

    # Recent commits in candidate files boost regression suspicion.
    if any(commits for commits in pack.commits_by_file.values()):
        regression_signals.append("Recent commits touch candidate files")

    if len(regression_signals) > len(intentional_signals):
        cls: Classification = "LIKELY_REGRESSION"
        conf = 0.55 + 0.1 * (len(regression_signals) - len(intentional_signals))
    elif len(intentional_signals) > len(regression_signals):
        cls = "LIKELY_INTENTIONAL"
        conf = 0.55 + 0.1 * (len(intentional_signals) - len(regression_signals))
    else:
        cls = "UNCLEAR"
        conf = 0.4

    return {
        "classification": cls,
        "confidence": round(min(conf, 0.9), 3),
        "intentional_signals": intentional_signals,
        "regression_signals": regression_signals,
        "reasoning": "Heuristic over docs + repro status + recent commits.",
    }


async def analyze_intent(bug: NormalizedBug, pack: ContextPack) -> dict[str, Any]:
    docs_brief = [{"title": d.title, "snippet": (d.body or d.snippet)[:600]} for d in pack.docs[:5]]
    commits_brief = {
        path: [{"sha": c.sha, "message": c.message, "files": c.files[:5]} for c in commits[:5]]
        for path, commits in pack.commits_by_file.items()
    }
    user = json.dumps(
        {
            "bug": bug.model_dump(),
            "docs": docs_brief,
            "recent_commits_per_file": commits_brief,
        },
        ensure_ascii=False,
    )
    system = (
        "You are a senior engineer doing root-cause analysis. "
        "Decide if the reported behavior is LIKELY_INTENTIONAL, LIKELY_REGRESSION, or UNCLEAR. "
        "Use the supplied docs, repro status, and recent commits. "
        "Return strict JSON: {classification, confidence (0-1), intentional_signals[], regression_signals[], reasoning}."
    )
    result = await complete_json(system, user)
    if not result or "classification" not in result:
        return _heuristic(bug, pack)
    if result["classification"] not in {"LIKELY_INTENTIONAL", "LIKELY_REGRESSION", "UNCLEAR"}:
        result["classification"] = "UNCLEAR"
    result.setdefault("confidence", 0.5)
    return result

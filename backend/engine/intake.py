"""Intake & normalization + manual repro evidence parsing."""
from __future__ import annotations

import re

from ..schemas import JiraIssue, NormalizedBug

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "and", "or", "but", "if", "then", "this", "that", "with", "as", "it",
    "i", "we", "you", "should", "from", "by", "at",
}


def _keywords(text: str, limit: int = 20) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_./-]{2,}", text or "")
    seen: dict[str, int] = {}
    for t in tokens:
        low = t.lower()
        if low in _STOP:
            continue
        seen[low] = seen.get(low, 0) + 1
    return [w for w, _ in sorted(seen.items(), key=lambda kv: -kv[1])[:limit]]


def normalize(issue: JiraIssue) -> NormalizedBug:
    repro_status = issue.repro_status or "uncertain"
    text_blob = " ".join(
        [
            issue.title,
            issue.description,
            issue.expected_behavior,
            issue.actual_behavior,
            issue.repro_notes,
            " ".join(issue.repro_steps),
            " ".join(issue.labels),
            " ".join(issue.components),
        ]
    )
    return NormalizedBug(
        bug_id=issue.key,
        title=issue.title,
        expected_behavior=issue.expected_behavior,
        actual_behavior=issue.actual_behavior,
        reporter_steps=issue.repro_steps,
        manual_repro={
            "status": repro_status,
            "environment": issue.environment,
            "steps_used": issue.repro_steps,
            "failing_step": issue.failing_step,
            "notes": issue.repro_notes,
        },
        attachments=issue.attachments,
        labels=issue.labels,
        components=issue.components,
        keywords=_keywords(text_blob),
    )


def repro_confidence(bug: NormalizedBug) -> float:
    status = (bug.manual_repro or {}).get("status", "uncertain")
    if status == "reproduced":
        base = 0.85
    elif status == "not_reproduced":
        base = 0.25
    else:
        base = 0.45
    if (bug.manual_repro or {}).get("steps_used"):
        base += 0.05
    if (bug.manual_repro or {}).get("environment"):
        base += 0.05
    return min(base, 0.99)

"""Recommendation engine + final report generation."""
from __future__ import annotations

from typing import Any

from ..schemas import (
    Classification,
    CodeCandidateOut,
    CommitCandidateOut,
    ContextArtifactOut,
    NormalizedBug,
    Recommendation,
)
from .context_retriever import ContextPack
from .intake import repro_confidence


def recommend(
    *,
    bug: NormalizedBug,
    classification: Classification,
    code_candidates: list[CodeCandidateOut],
    commit_candidates: list[CommitCandidateOut],
) -> Recommendation:
    repro = (bug.manual_repro or {}).get("status", "uncertain")
    if repro == "not_reproduced":
        return "NEEDS_MORE_REPRO_DATA"
    if classification == "LIKELY_INTENTIONAL":
        return "LIKELY_EXPECTED_BEHAVIOR"
    if classification == "LIKELY_REGRESSION":
        if commit_candidates and commit_candidates[0].confidence > 0.7:
            return "ASSIGN_TO_COMMIT_OWNER"
        return "LIKELY_REGRESSION"
    if not code_candidates:
        return "MANUAL_DEEP_DIVE_REQUIRED"
    return "LEAD_REVIEW"


def build_artifacts(pack: ContextPack) -> list[ContextArtifactOut]:
    arts: list[ContextArtifactOut] = []
    for d in pack.docs:
        arts.append(ContextArtifactOut(
            source_type="confluence",
            source_id=d.id,
            title=d.title,
            url=d.url,
            relevance_score=0.7,
            metadata={"space": d.space, "snippet": d.snippet[:240]},
        ))
    for r in pack.related_issues:
        arts.append(ContextArtifactOut(
            source_type="jira",
            source_id=r.key,
            title=r.title,
            url=r.url,
            relevance_score=0.6,
            metadata={"labels": r.labels, "components": r.components},
        ))
    for hit in pack.code_hits:
        arts.append(ContextArtifactOut(
            source_type="github",
            source_id=f"{hit.repo}:{hit.path}",
            title=hit.path,
            url=f"https://github.com/{hit.repo}/blob/HEAD/{hit.path}",
            relevance_score=hit.score,
            metadata={"snippet": hit.snippet[:240], "symbol": hit.symbol},
        ))
    return arts


def build_report(
    *,
    bug: NormalizedBug,
    pack: ContextPack,
    classification: Classification,
    intent_payload: dict[str, Any],
    code_candidates: list[CodeCandidateOut],
    commit_candidates: list[CommitCandidateOut],
    recommendation: Recommendation,
) -> dict[str, Any]:
    repro_conf = repro_confidence(bug)
    intent_conf = float(intent_payload.get("confidence", 0.5))
    overall = round((repro_conf + intent_conf) / 2.0, 3)

    md_lines: list[str] = []
    md_lines.append(f"# Investigation Report — {bug.bug_id}")
    md_lines.append("")
    md_lines.append(f"**Title:** {bug.title}")
    md_lines.append(f"**Classification:** {classification}  ")
    md_lines.append(f"**Recommendation:** {recommendation}  ")
    md_lines.append(f"**Confidence:** {overall}")
    md_lines.append("")
    md_lines.append("## Manual Reproduction")
    md_lines.append(f"- Status: `{(bug.manual_repro or {}).get('status', 'uncertain')}`")
    env = (bug.manual_repro or {}).get("environment") or {}
    if env:
        md_lines.append(f"- Environment: `{env}`")
    if bug.reporter_steps:
        md_lines.append("- Steps:")
        for s in bug.reporter_steps:
            md_lines.append(f"  - {s}")
    md_lines.append("")
    md_lines.append("## Likely Code Locations")
    if not code_candidates:
        md_lines.append("_None identified._")
    for c in code_candidates:
        md_lines.append(f"- `{c.repo}` → `{c.file_path}` ({c.symbol or '—'}) — confidence {c.confidence}")
        md_lines.append(f"  - {c.rationale}")
    md_lines.append("")
    md_lines.append("## Suspicious Commits / PRs")
    if not commit_candidates:
        md_lines.append("_None identified._")
    for cc in commit_candidates:
        pr = f" (PR #{cc.pr_number})" if cc.pr_number else ""
        md_lines.append(f"- `{cc.repo}@{cc.commit_sha[:7]}`{pr} — confidence {cc.confidence}")
        md_lines.append(f"  - {cc.rationale}")
    md_lines.append("")
    md_lines.append("## Intent Analysis")
    md_lines.append(intent_payload.get("reasoning", ""))
    if intent_payload.get("regression_signals"):
        md_lines.append("**Regression signals:**")
        for s in intent_payload["regression_signals"]:
            md_lines.append(f"- {s}")
    if intent_payload.get("intentional_signals"):
        md_lines.append("**Intentional signals:**")
        for s in intent_payload["intentional_signals"]:
            md_lines.append(f"- {s}")
    md_lines.append("")
    md_lines.append("## Supporting Documents")
    for d in pack.docs[:5]:
        md_lines.append(f"- [{d.title}]({d.url})")
    md_lines.append("")
    md_lines.append("## Related Jira Tickets")
    for r in pack.related_issues[:5]:
        md_lines.append(f"- [{r.key}]({r.url}) — {r.title}")

    return {
        "summary_markdown": "\n".join(md_lines),
        "classification": classification,
        "recommendation": recommendation,
        "confidence": overall,
        "payload": {
            "bug": bug.model_dump(),
            "intent": intent_payload,
            "code_candidates": [c.model_dump() for c in code_candidates],
            "commit_candidates": [c.model_dump() for c in commit_candidates],
        },
    }

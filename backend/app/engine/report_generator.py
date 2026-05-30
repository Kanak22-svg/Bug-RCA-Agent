"""Report Generator.
Assembles all investigation findings into a structured report.
"""
from datetime import datetime


class ReportGenerator:

    async def generate(self, bug_snapshot: dict, code_candidates: list[dict],
                       suspicious_commits: list[dict], intent_result: dict,
                       recommendation: dict, related_issues: list[dict],
                       confluence_docs: list[dict]) -> dict:
        """Generate the final investigation report.

        Returns a complete report dict ready for storage and display.
        """
        classification = intent_result.get("classification", "UNCLEAR")
        confidence = intent_result.get("confidence", 0.5)

        # Executive summary
        executive_summary = self._build_executive_summary(
            bug_snapshot, classification, confidence,
            code_candidates, suspicious_commits, confluence_docs
        )

        # Key findings
        key_findings = self._build_key_findings(
            bug_snapshot, code_candidates, suspicious_commits,
            related_issues, confluence_docs
        )

        # Evidence timeline
        evidence_timeline = self._build_evidence_timeline(
            bug_snapshot, code_candidates, suspicious_commits,
            related_issues, confluence_docs
        )

        return {
            "executive_summary": executive_summary,
            "classification": classification,
            "confidence_score": round(confidence, 2),
            "recommendation": recommendation.get("recommendation", "MANUAL_DEEP_DIVE"),
            "recommendation_detail": recommendation.get("recommendation_detail", ""),
            "key_findings_json": key_findings,
            "suggested_action": recommendation.get("recommendation_detail", ""),
            "suggested_code_direction": recommendation.get("suggested_code_direction"),
            "suggested_owner": recommendation.get("suggested_owner"),
            "evidence_timeline_json": evidence_timeline,
        }

    def _build_executive_summary(self, bug: dict, classification: str,
                                  confidence: float, candidates: list[dict],
                                  suspects: list[dict], docs: list[dict]) -> str:
        """Build the AI-generated executive summary paragraph."""
        title = bug.get("title", "Unknown bug")
        component = bug.get("component", "unknown component")

        # Classification text
        if classification == "LIKELY_REGRESSION":
            class_text = "classified as a LIKELY REGRESSION"
        elif classification == "LIKELY_INTENTIONAL":
            class_text = "classified as LIKELY INTENTIONAL behavior"
        else:
            class_text = "classification is UNCLEAR and needs further investigation"

        parts = [f"Investigation of \"{title}\" in the {component} module."]

        if candidates:
            top = candidates[0]
            parts.append(
                f"The most likely code location is `{top.get('symbol', 'unknown')}` "
                f"in `{top.get('file_path', 'unknown')}` "
                f"(confidence: {int(top.get('confidence', 0) * 100)}%)."
            )

        if suspects:
            top_suspect = suspects[0]
            pr_num = top_suspect.get("pr_number")
            author = top_suspect.get("author", "unknown")
            if pr_num:
                parts.append(
                    f"The most suspicious change is PR #{pr_num} "
                    f"(\"{top_suspect.get('pr_title', '')}\") by @{author}, "
                    f"which modified the affected code area."
                )

        # Check for contradicting docs
        contradicting = [d for d in docs if d.get("relevance_tag") == "CONTRADICTS"]
        if contradicting:
            doc = contradicting[0]
            parts.append(
                f"The Confluence document \"{doc.get('title', '')}\" directly contradicts "
                f"the current behavior, supporting the regression classification."
            )

        parts.append(
            f"This issue is {class_text} with {int(confidence * 100)}% confidence."
        )

        return " ".join(parts)

    def _build_key_findings(self, bug: dict, candidates: list[dict],
                            suspects: list[dict], related: list[dict],
                            docs: list[dict]) -> list[dict]:
        """Build the key findings list for the report."""
        findings = []

        if candidates:
            top = candidates[0]
            findings.append({
                "label": "Most likely file",
                "value": top.get("file_path", "unknown"),
                "icon": "file"
            })
            findings.append({
                "label": "Most likely function",
                "value": top.get("symbol", "unknown"),
                "icon": "function"
            })

        if suspects:
            top = suspects[0]
            findings.append({
                "label": "Suspicious commit",
                "value": f"{top.get('commit_sha', '?')[:7]} by @{top.get('author', 'unknown')} ({top.get('committed_at', '')[:10] if top.get('committed_at') else 'unknown date'})",
                "icon": "commit"
            })
            if top.get("pr_number"):
                findings.append({
                    "label": "Suspicious PR",
                    "value": f"#{top['pr_number']} \"{top.get('pr_title', '')}\"",
                    "icon": "pr"
                })

        findings.append({
            "label": "Related tickets",
            "value": f"{len(related)} found",
            "icon": "ticket"
        })

        findings.append({
            "label": "Docs consulted",
            "value": f"{len(docs)}",
            "icon": "doc"
        })

        return findings

    def _build_evidence_timeline(self, bug: dict, candidates: list[dict],
                                  suspects: list[dict], related: list[dict],
                                  docs: list[dict]) -> list[dict]:
        """Build chronological evidence timeline."""
        events = []

        # Add doc creation events
        for doc in docs:
            events.append({
                "date": doc.get("last_updated", ""),
                "type": "doc",
                "icon": "doc",
                "title": doc.get("title", ""),
                "description": f"Documentation in {doc.get('space', 'unknown')} space",
                "is_suspect": doc.get("relevance_tag") == "CONTRADICTS",
            })

        # Add related issue events
        for issue in related:
            events.append({
                "date": issue.get("created_at", ""),
                "type": "ticket",
                "icon": "ticket",
                "title": f"{issue.get('key', '?')}: {issue.get('title', '')}",
                "description": f"Type: {issue.get('relation_type', 'related')}",
                "is_suspect": False,
            })

        # Add commit/PR events
        for suspect in suspects:
            events.append({
                "date": suspect.get("committed_at", ""),
                "type": "commit",
                "icon": "commit" if not suspect.get("pr_number") else "pr",
                "title": f"PR #{suspect['pr_number']}: {suspect.get('pr_title', '')}" if suspect.get("pr_number") else f"Commit {suspect.get('commit_sha', '?')[:7]}",
                "description": suspect.get("commit_message", "").split("\n")[0],
                "is_suspect": suspect.get("suspicion_level") == "high",
            })

        # Add the bug creation itself
        events.append({
            "date": bug.get("created_at", bug.get("environment_json", {}).get("deploy_date", "")),
            "type": "bug",
            "icon": "bug",
            "title": f"Bug reported: {bug.get('title', '')}",
            "description": f"Reporter: {bug.get('reporter', 'unknown')}",
            "is_suspect": False,
        })

        # Add investigation event
        events.append({
            "date": datetime.now().isoformat(),
            "type": "investigation",
            "icon": "search",
            "title": "Investigation run",
            "description": "This analysis",
            "is_suspect": False,
        })

        # Sort by date
        events.sort(key=lambda e: e.get("date", "") or "")

        return events

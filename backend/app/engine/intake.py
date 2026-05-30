"""Intake & Normalization Module.
Takes raw issue data and normalizes it into a structured bug snapshot.
"""
from typing import Optional


class IntakeModule:

    async def normalize_bug(self, issue_data: dict) -> dict:
        """Normalize raw Jira issue data into a structured bug snapshot."""
        return {
            "title": issue_data.get("title", ""),
            "description": issue_data.get("description", ""),
            "expected_behavior": issue_data.get("expected_behavior", ""),
            "actual_behavior": issue_data.get("actual_behavior", ""),
            "environment_json": issue_data.get("environment", {}),
            "priority": issue_data.get("priority", "Medium"),
            "severity": issue_data.get("severity", ""),
            "component": issue_data.get("component", ""),
            "labels_json": issue_data.get("labels", []),
            "assignee": issue_data.get("assignee", ""),
            "assigned_team": issue_data.get("assigned_team", ""),
            "reporter": issue_data.get("reporter", ""),
            "status": issue_data.get("status", ""),
            "linked_issues_json": issue_data.get("linked_issues", []),
            "comments_json": issue_data.get("comments", []),
            "attachments_json": issue_data.get("attachments", []),
        }

    def extract_keywords(self, bug_snapshot: dict) -> list[str]:
        """Extract searchable keywords from the bug snapshot for code localization."""
        keywords = []

        # From title
        title = bug_snapshot.get("title", "")
        for word in title.lower().split():
            if len(word) > 3 and word not in {"button", "should", "users", "that", "this", "when", "with", "from", "have", "been", "does", "into"}:
                keywords.append(word)

        # From component
        component = bug_snapshot.get("component", "")
        if component:
            keywords.append(component.lower())

        # From labels
        labels = bug_snapshot.get("labels_json", [])
        for label in labels:
            if label not in ("bug", "enhancement", "feature"):
                keywords.append(label.lower())

        # Extract likely code-related terms
        desc = bug_snapshot.get("description", "") + " " + bug_snapshot.get("actual_behavior", "")
        code_terms = []
        for word in desc.split():
            # CamelCase or contains dots or slashes (likely code references)
            if any(c.isupper() for c in word[1:]) or "." in word or "/" in word:
                code_terms.append(word.strip(".,;:()"))
        keywords.extend(code_terms)

        return list(set(keywords))

    def extract_module_hints(self, bug_snapshot: dict) -> list[str]:
        """Extract hints about which code module/area is likely affected."""
        hints = []

        component = bug_snapshot.get("component", "")
        if component:
            hints.append(component.lower())

        labels = bug_snapshot.get("labels_json", [])
        for label in labels:
            if "-" in label:
                parts = label.split("-")
                hints.extend(parts)
            hints.append(label)

        # Look for module references in description
        desc = (bug_snapshot.get("description", "") + " " +
                bug_snapshot.get("title", "")).lower()

        ui_keywords = ["button", "page", "dialog", "modal", "form", "panel", "toolbar"]
        api_keywords = ["endpoint", "api", "request", "response", "route"]

        for kw in ui_keywords:
            if kw in desc:
                hints.append("frontend")
                break
        for kw in api_keywords:
            if kw in desc:
                hints.append("backend")
                break

        return list(set(hints))

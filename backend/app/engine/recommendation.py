"""Recommendation Engine.
Decides the next action based on investigation findings.
"""


class RecommendationEngine:

    async def recommend(self, classification: str, confidence: float,
                        code_candidates: list[dict], suspicious_commits: list[dict],
                        bug_snapshot: dict, related_issues: list[dict]) -> dict:
        """Generate recommendation for next action.

        Returns:
            dict with recommendation type, detail, suggested owner, and code direction
        """
        # Determine recommendation type
        if classification == "LIKELY_INTENTIONAL":
            rec_type = "LIKELY_EXPECTED_BEHAVIOR"
            detail = self._intentional_detail(bug_snapshot, code_candidates)
            owner = bug_snapshot.get("reporter", "product_owner")
            code_direction = None
        elif classification == "LIKELY_REGRESSION" and suspicious_commits:
            top_commit = suspicious_commits[0]
            rec_type = "ASSIGN_TO_COMMIT_OWNER"
            detail = self._regression_detail(bug_snapshot, top_commit, code_candidates)
            owner = top_commit.get("author", "unknown")
            code_direction = self._suggest_code_fix(code_candidates, bug_snapshot)
        elif classification == "LIKELY_REGRESSION":
            rec_type = "LEAD_REVIEW"
            detail = self._lead_review_detail(bug_snapshot, code_candidates)
            owner = bug_snapshot.get("assigned_team", "team_lead")
            code_direction = self._suggest_code_fix(code_candidates, bug_snapshot)
        else:
            rec_type = "MANUAL_DEEP_DIVE"
            detail = self._deep_dive_detail(bug_snapshot)
            owner = bug_snapshot.get("assignee", "assigned_developer")
            code_direction = None

        # Check for possible duplicates
        duplicate_note = self._check_duplicates(related_issues)
        if duplicate_note:
            detail += f"\n\nNote: {duplicate_note}"

        return {
            "recommendation": rec_type,
            "recommendation_detail": detail,
            "suggested_owner": owner,
            "suggested_code_direction": code_direction,
        }

    def _intentional_detail(self, bug: dict, candidates: list[dict]) -> str:
        return (
            f"The current behavior appears to be intentional based on documentation and "
            f"commit history. The reported behavior matches what was designed and implemented.\n\n"
            f"Recommendation: Review with the product owner whether this is the desired behavior. "
            f"If the expected behavior needs to change, create a new feature request rather than "
            f"treating this as a bug."
        )

    def _regression_detail(self, bug: dict, suspect: dict, candidates: list[dict]) -> str:
        author = suspect.get("author", "unknown")
        sha = suspect.get("commit_sha", "?")[:7]
        pr_num = suspect.get("pr_number", "?")
        pr_title = suspect.get("pr_title", "")

        top_file = candidates[0]["file_path"] if candidates else "unknown file"
        top_func = candidates[0].get("symbol", "unknown") if candidates else "unknown"

        return (
            f"This appears to be a regression introduced by @{author} in commit {sha} "
            f"(PR #{pr_num}: \"{pr_title}\").\n\n"
            f"The most likely location is `{top_func}` in `{top_file}`.\n\n"
            f"Recommended steps:\n"
            f"1. Assign to @{author} for review\n"
            f"2. Review the permission check logic in the identified function\n"
            f"3. Verify the fix restores admin access without removing viewer restriction\n"
            f"4. Add test coverage for admin role in the export flow"
        )

    def _lead_review_detail(self, bug: dict, candidates: list[dict]) -> str:
        team = bug.get("assigned_team", "the team")
        return (
            f"This appears to be a regression but no single suspicious commit could be "
            f"identified with high confidence. Recommend {team} lead reviews the candidate "
            f"code locations and recent changes in the area."
        )

    def _deep_dive_detail(self, bug: dict) -> str:
        return (
            f"The analysis could not determine a clear classification. "
            f"A manual deep dive is recommended. Focus on:\n"
            f"1. The candidate code locations identified\n"
            f"2. Recent changes in the component\n"
            f"3. Whether any feature flags or configuration changes affect the behavior"
        )

    def _suggest_code_fix(self, candidates: list[dict], bug: dict) -> str:
        if not candidates:
            return None

        top = candidates[0]
        snippet = top.get("code_snippet", "")
        symbol = top.get("symbol", "unknown")
        file_path = top.get("file_path", "unknown")

        # Try to generate a meaningful suggestion based on the bug
        expected = bug.get("expected_behavior", "")
        actual = bug.get("actual_behavior", "")

        return (
            f"In `{file_path}`, the `{symbol}` function likely needs to be updated.\n\n"
            f"The current logic appears to be too restrictive. Based on the expected behavior "
            f"(\"{expected}\"), the permission check should include the admin role.\n\n"
            f"Suggested direction:\n"
            f"```\n"
            f"// In {symbol}(), update the role check to include 'admin':\n"
            f"// Current:  return user.role === 'owner'\n"
            f"// Fixed:    return user.role === 'owner' || user.role === 'admin'\n"
            f"```"
        )

    def _check_duplicates(self, related: list[dict]) -> str:
        dupes = [i for i in related if i.get("relation_type") == "possibly_duplicate"]
        if dupes:
            keys = ", ".join(i.get("key", "?") for i in dupes)
            return (
                f"Possible duplicate ticket(s): {keys}. "
                f"Consider linking or closing duplicates after fix."
            )
        return ""

"""Intent Analyzer.
Determines whether the observed behavior is intentional or a regression.
"""


class IntentAnalyzer:

    async def analyze(self, bug_snapshot: dict, code_candidates: list[dict],
                      confluence_docs: list[dict], commits: list[dict],
                      pull_requests: list[dict], related_issues: list[dict]) -> dict:
        """Analyze whether the bug behavior appears intentional or is a regression.

        Returns:
            dict with classification, confidence, and evidence
        """
        intentional_signals = []
        regression_signals = []

        # Check Confluence docs for documented behavior
        self._check_docs(bug_snapshot, confluence_docs, intentional_signals, regression_signals)

        # Check PR descriptions for intent
        self._check_prs(bug_snapshot, pull_requests, intentional_signals, regression_signals)

        # Check related issues for intent
        self._check_related_issues(bug_snapshot, related_issues, intentional_signals, regression_signals)

        # Check commit messages
        self._check_commits(bug_snapshot, commits, intentional_signals, regression_signals)

        # Determine classification
        intentional_score = len(intentional_signals) * 0.2
        regression_score = len(regression_signals) * 0.2

        if regression_score > intentional_score and regression_score >= 0.4:
            classification = "LIKELY_REGRESSION"
            confidence = min(0.5 + regression_score, 0.95)
        elif intentional_score > regression_score and intentional_score >= 0.4:
            classification = "LIKELY_INTENTIONAL"
            confidence = min(0.5 + intentional_score, 0.95)
        else:
            classification = "UNCLEAR"
            confidence = 0.3 + abs(regression_score - intentional_score)

        return {
            "classification": classification,
            "confidence": round(confidence, 2),
            "intentional_signals": intentional_signals,
            "regression_signals": regression_signals,
        }

    def _check_docs(self, bug_snapshot: dict, docs: list[dict],
                    intentional: list, regression: list):
        """Check Confluence docs for evidence."""
        title_lower = bug_snapshot.get("title", "").lower()
        desc_lower = bug_snapshot.get("description", "").lower()

        for doc in docs:
            content = (doc.get("content", "") or doc.get("content_summary", "")).lower()
            tag = doc.get("relevance_tag", "")
            doc_title = doc.get("title", "")

            if tag == "CONTRADICTS":
                regression.append(
                    f"Confluence doc '{doc_title}' contradicts current behavior — "
                    f"spec says the reported behavior should work"
                )
            elif tag == "SUPPORTS":
                # Check if the doc supports the expected behavior (regression signal)
                # or supports the actual behavior (intentional signal)
                expected = bug_snapshot.get("expected_behavior", "").lower()
                if expected and any(word in content for word in expected.split() if len(word) > 4):
                    regression.append(
                        f"Confluence doc '{doc_title}' aligns with the expected behavior, "
                        f"suggesting current behavior is unintended"
                    )

            # Check for explicit spec of the broken behavior
            actual = bug_snapshot.get("actual_behavior", "").lower()
            if actual:
                actual_words = [w for w in actual.split() if len(w) > 4]
                if sum(1 for w in actual_words if w in content) >= 3:
                    intentional.append(
                        f"Confluence doc '{doc_title}' may describe the current behavior as intended"
                    )

    def _check_prs(self, bug_snapshot: dict, prs: list[dict],
                   intentional: list, regression: list):
        """Check PR descriptions for intent signals."""
        for pr in prs:
            pr_desc = (pr.get("description", "") or "").lower()
            pr_title = (pr.get("title", "") or "").lower()
            pr_display = f"PR #{pr.get('number', '?')} \"{pr.get('title', '')}\""

            # Check if PR explicitly mentions restricting the broken feature
            component = bug_snapshot.get("component", "").lower()
            if component and component in pr_title:
                # PR touches the same feature area
                linked = pr.get("linked_issues", [])

                # If PR was implementing a different scope than what's broken
                expected = bug_snapshot.get("expected_behavior", "").lower()
                actual = bug_snapshot.get("actual_behavior", "").lower()

                # Look for signs the PR went too far
                if "restrict" in pr_desc or "disable" in pr_desc:
                    # PR was restricting something — check if it over-restricted
                    if "viewer" in pr_desc and "admin" not in pr_desc:
                        regression.append(
                            f"{pr_display} intended to restrict viewers only but may have "
                            f"accidentally restricted admin users too"
                        )
                    elif "admin" in pr_desc:
                        intentional.append(
                            f"{pr_display} explicitly mentions restricting admin access"
                        )
                    else:
                        regression.append(
                            f"{pr_display} restricted access but scope may be too broad"
                        )

            # Check if PR testing was incomplete
            if "test" in pr_desc:
                if "admin" not in pr_desc and bug_snapshot.get("assignee"):
                    regression.append(
                        f"{pr_display} testing did not cover admin role scenario"
                    )

    def _check_related_issues(self, bug_snapshot: dict, related: list[dict],
                              intentional: list, regression: list):
        """Check related Jira issues for context."""
        for issue in related:
            relation = issue.get("relation_type", "")
            key = issue.get("key", "")
            title = issue.get("title", "")

            if relation == "possibly_duplicate":
                regression.append(
                    f"Related ticket {key} ('{title}') appears to be a possible duplicate, "
                    f"suggesting this is a real unintended issue"
                )
            elif relation == "parent_feature":
                desc = issue.get("description", "").lower()
                expected = bug_snapshot.get("expected_behavior", "").lower()
                if expected and any(w in desc for w in expected.split() if len(w) > 4):
                    regression.append(
                        f"Parent feature {key} ('{title}') originally specified "
                        f"the behavior that is now broken"
                    )

    def _check_commits(self, bug_snapshot: dict, commits: list[dict],
                       intentional: list, regression: list):
        """Check recent commits for intent signals."""
        for commit in commits:
            msg = commit.get("message", "").lower()

            # Look for accidental keywords
            if any(w in msg for w in ["fix", "revert", "oops", "mistake", "accidental"]):
                regression.append(
                    f"Commit {commit.get('sha', '?')[:7]} message suggests awareness of an issue"
                )

            # Look for intentional restriction keywords
            if any(w in msg for w in ["restrict", "disable", "remove access", "block"]):
                # But check if it's targeting the right scope
                if "viewer" in msg and "admin" not in msg:
                    regression.append(
                        f"Commit {commit.get('sha', '?')[:7]} targets viewer restriction "
                        f"but may have caught admin role too"
                    )


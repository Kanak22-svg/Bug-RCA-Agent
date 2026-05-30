"""Regression Finder.
Identifies suspicious commits and PRs that may have caused the bug.
"""
from datetime import datetime


class RegressionFinder:

    async def find_suspects(self, code_candidates: list[dict],
                            commits: list[dict], pull_requests: list[dict],
                            bug_snapshot: dict) -> list[dict]:
        """Find suspicious commits and PRs that may have caused the regression.

        Returns ranked list of suspicious commits with confidence.
        """
        suspects = []
        seen_shas = set()

        # Get files from top code candidates
        candidate_files = set()
        for c in code_candidates[:5]:
            candidate_files.add(c.get("file_path", ""))

        # Score each commit
        for commit in commits:
            sha = commit.get("sha", "")
            if sha in seen_shas:
                continue
            seen_shas.add(sha)

            score = self._score_commit(commit, candidate_files, bug_snapshot)
            if score > 0.1:
                suspicion = "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"

                # Find associated PR
                pr_number = commit.get("pr_number")
                pr_data = None
                if pr_number:
                    for pr in pull_requests:
                        if pr.get("number") == pr_number:
                            pr_data = pr
                            break

                suspects.append({
                    "repo": commit.get("repo", ""),
                    "commit_sha": sha,
                    "pr_number": pr_number,
                    "pr_title": pr_data.get("title") if pr_data else None,
                    "author": commit.get("author", ""),
                    "confidence": round(score, 2),
                    "suspicion_level": suspicion,
                    "rationale": self._generate_rationale(commit, pr_data, candidate_files, bug_snapshot),
                    "commit_message": commit.get("message", ""),
                    "committed_at": commit.get("date"),
                    "files_changed": commit.get("files_changed", []),
                })

        # Sort by confidence descending
        suspects.sort(key=lambda x: x["confidence"], reverse=True)
        return suspects

    def _score_commit(self, commit: dict, candidate_files: set, bug_snapshot: dict) -> float:
        """Score how suspicious a commit is."""
        score = 0.0

        # Files overlap with code candidates
        changed = set(commit.get("files_changed", []))
        overlap = changed & candidate_files
        if overlap:
            score += 0.3 * len(overlap)

        # Recency — more recent = more suspicious
        date_str = commit.get("date", "")
        if date_str:
            try:
                if isinstance(date_str, str):
                    commit_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    now = datetime.now(commit_date.tzinfo)
                    days_ago = (now - commit_date).days
                    if days_ago <= 7:
                        score += 0.25
                    elif days_ago <= 14:
                        score += 0.15
                    elif days_ago <= 30:
                        score += 0.05
            except (ValueError, TypeError):
                pass

        # Message relevance
        msg = commit.get("message", "").lower()
        component = bug_snapshot.get("component", "").lower()
        keywords = [w.lower() for w in bug_snapshot.get("title", "").split() if len(w) > 3]

        if component and component in msg:
            score += 0.1

        keyword_hits = sum(1 for kw in keywords if kw in msg)
        score += min(keyword_hits * 0.05, 0.15)

        # Restriction/permission changes are extra suspicious for permission bugs
        if any(w in msg for w in ["restrict", "permission", "role", "access", "disable"]):
            labels = bug_snapshot.get("labels_json", [])
            if "permissions" in labels or "permission" in bug_snapshot.get("title", "").lower():
                score += 0.2

        return min(score, 0.95)

    def _generate_rationale(self, commit: dict, pr_data: dict,
                            candidate_files: set, bug_snapshot: dict) -> str:
        """Generate human-readable rationale for why this commit is suspicious."""
        parts = []

        changed = set(commit.get("files_changed", []))
        overlap = changed & candidate_files
        if overlap:
            parts.append(f"Changed suspect file(s): {', '.join(overlap)}")

        if pr_data:
            pr_desc = pr_data.get("description", "")
            if "restrict" in pr_desc.lower() or "disable" in pr_desc.lower():
                parts.append(f"PR #{pr_data['number']} explicitly restricts access")

            testing = pr_data.get("description", "")
            if "admin" not in testing.lower():
                parts.append("PR testing did not verify admin role scenario")

        msg = commit.get("message", "")
        if msg:
            parts.append(f"Commit message: \"{msg.split(chr(10))[0]}\"")

        return ". ".join(parts) if parts else "Matched via file change analysis"

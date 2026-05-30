"""Code Localization Engine.
Maps bug data to candidate files and functions in the codebase.
"""
from app.providers.base import CodeProvider


class CodeLocalizationEngine:

    def __init__(self, code_provider: CodeProvider):
        self.code_provider = code_provider

    async def localize(self, bug_snapshot: dict, keywords: list[str],
                       module_hints: list[str], repo: str,
                       recent_commits: list[dict] = None) -> list[dict]:
        """Find candidate code locations for the bug.

        Returns ranked list of candidates with confidence scores.
        """
        candidates = []
        seen_paths = set()

        # Strategy 1: Search by keywords from bug
        for keyword in keywords[:10]:  # limit to avoid too many searches
            try:
                results = await self.code_provider.search_code(keyword, repo)
                for result in results:
                    path = result.get("path", "")
                    if path not in seen_paths:
                        seen_paths.add(path)
                        candidates.append({
                            "repo": result.get("repo", repo),
                            "file_path": path,
                            "match_keyword": keyword,
                            "language": result.get("language"),
                            "last_modified": result.get("last_modified"),
                        })
            except Exception:
                continue

        # Strategy 2: Look at files changed in recent commits
        if recent_commits:
            for commit in recent_commits[:10]:
                for file_path in commit.get("files_changed", []):
                    if file_path not in seen_paths:
                        seen_paths.add(file_path)
                        candidates.append({
                            "repo": commit.get("repo", repo),
                            "file_path": file_path,
                            "match_keyword": "recent_change",
                            "last_modified": commit.get("date"),
                        })

        # Score and rank candidates
        scored = []
        for candidate in candidates:
            score = await self._score_candidate(candidate, bug_snapshot, keywords, module_hints, recent_commits)
            candidate["confidence"] = score
            scored.append(candidate)

        # Sort by confidence descending
        scored.sort(key=lambda x: x["confidence"], reverse=True)

        # Enrich top candidates with file content and symbol detection
        enriched = []
        for i, candidate in enumerate(scored[:5]):
            try:
                file_data = await self.code_provider.get_file(candidate["repo"], candidate["file_path"])
                content = file_data.get("content", "")
                symbol = self._find_likely_symbol(content, keywords)
                suspect_line = self._find_suspect_line(content, keywords)

                enriched.append({
                    "rank": i + 1,
                    "repo": candidate["repo"],
                    "file_path": candidate["file_path"],
                    "symbol": symbol,
                    "confidence": round(candidate["confidence"], 2),
                    "rationale": self._generate_rationale(candidate, bug_snapshot),
                    "code_snippet": content,
                    "suspect_line": suspect_line,
                })
            except Exception:
                enriched.append({
                    "rank": i + 1,
                    "repo": candidate["repo"],
                    "file_path": candidate["file_path"],
                    "symbol": None,
                    "confidence": round(candidate["confidence"], 2),
                    "rationale": self._generate_rationale(candidate, bug_snapshot),
                    "code_snippet": None,
                    "suspect_line": None,
                })

        return enriched

    async def _score_candidate(self, candidate: dict, bug_snapshot: dict,
                               keywords: list[str], module_hints: list[str],
                               recent_commits: list[dict] = None) -> float:
        """Score a candidate file's likelihood of being the bug location."""
        score = 0.0
        path_lower = candidate["file_path"].lower()

        # Component/module match
        for hint in module_hints:
            if hint in path_lower:
                score += 0.25

        # Keyword match in path
        keyword_matches = sum(1 for kw in keywords if kw in path_lower)
        score += min(keyword_matches * 0.15, 0.45)

        # Recently modified (higher suspicion)
        if candidate.get("match_keyword") == "recent_change":
            score += 0.1

        # File was changed in recent commits that mention related issues
        if recent_commits:
            for commit in recent_commits:
                if candidate["file_path"] in commit.get("files_changed", []):
                    msg = commit.get("message", "").lower()
                    # Check if commit mentions related keywords
                    if any(kw in msg for kw in keywords):
                        score += 0.2
                    else:
                        score += 0.05

        # Cap at 0.95
        return min(score, 0.95)

    def _find_likely_symbol(self, content: str, keywords: list[str]) -> str:
        """Find the most likely function/class name in the file related to the bug."""
        lines = content.split("\n")
        best_symbol = None
        best_score = 0

        for line in lines:
            # Detect function/method definitions
            symbol = None
            if "function " in line:
                parts = line.split("function ")[1].split("(")[0].strip()
                symbol = parts
            elif "def " in line:
                parts = line.split("def ")[1].split("(")[0].strip()
                symbol = parts
            elif "func " in line:
                parts = line.split("func ")[1].split("(")[0].strip()
                symbol = parts
            elif "const " in line and "=>" in line:
                parts = line.split("const ")[1].split("=")[0].strip()
                symbol = parts

            if symbol:
                symbol_lower = symbol.lower()
                score = sum(1 for kw in keywords if kw in symbol_lower)
                if score > best_score:
                    best_score = score
                    best_symbol = symbol

        return best_symbol or "unknown"

    def _find_suspect_line(self, content: str, keywords: list[str]) -> int:
        """Find the most suspicious line number in the file."""
        lines = content.split("\n")
        best_line = 1
        best_score = 0

        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            score = sum(1 for kw in keywords if kw in line_lower)
            # Bonus for lines with comparisons or returns (likely where logic bugs live)
            if "===" in line or "==" in line or "return " in line:
                score += 0.5
            if score > best_score:
                best_score = score
                best_line = i

        return best_line

    def _generate_rationale(self, candidate: dict, bug_snapshot: dict) -> str:
        """Generate a human-readable rationale for why this file is suspicious."""
        parts = []
        path = candidate["file_path"]

        component = bug_snapshot.get("component", "")
        if component and component.lower() in path.lower():
            parts.append(f"File is in the '{component}' module mentioned in the bug")

        title = bug_snapshot.get("title", "")
        title_words = [w.lower() for w in title.split() if len(w) > 3]
        path_lower = path.lower()
        matching = [w for w in title_words if w in path_lower]
        if matching:
            parts.append(f"File path matches bug keywords: {', '.join(matching)}")

        if candidate.get("match_keyword") == "recent_change":
            parts.append("File was recently changed in a relevant commit")

        if candidate.get("last_modified"):
            parts.append(f"Last modified: {candidate['last_modified']}")

        return ". ".join(parts) if parts else "Matched via keyword search"

"""Investigation Orchestrator.
Central coordinator that runs the investigation pipeline step by step.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

from app.providers.base import IssueProvider, DocsProvider, CodeProvider
from app.engine.intake import IntakeModule
from app.engine.localization import CodeLocalizationEngine
from app.engine.intent_analyzer import IntentAnalyzer
from app.engine.regression_finder import RegressionFinder
from app.engine.recommendation import RecommendationEngine
from app.engine.report_generator import ReportGenerator
from app.engine.llm_analyzer import LLMAnalyzer
from app.config import settings

logger = logging.getLogger(__name__)


PIPELINE_STEPS = [
    {"number": 1, "name": "Fetching Jira issue details"},
    {"number": 2, "name": "Finding related Jira tickets"},
    {"number": 3, "name": "Retrieving Confluence docs"},
    {"number": 4, "name": "Searching GitHub code"},
    {"number": 5, "name": "Analyzing code locations"},
    {"number": 6, "name": "Checking if behavior is intentional"},
    {"number": 7, "name": "Finding suspicious commits"},
    {"number": 8, "name": "Generating final report"},
]


class InvestigationOrchestrator:
    """Runs the complete investigation pipeline."""

    def __init__(self, issue_provider: IssueProvider,
                 docs_provider: DocsProvider,
                 code_provider: CodeProvider):
        self.issue_provider = issue_provider
        self.docs_provider = docs_provider
        self.code_provider = code_provider

        self.intake = IntakeModule()
        self.localizer = CodeLocalizationEngine(code_provider)
        self.intent_analyzer = IntentAnalyzer()
        self.regression_finder = RegressionFinder()
        self.recommender = RecommendationEngine()
        self.report_gen = ReportGenerator()
        self.llm = LLMAnalyzer(api_key=settings.ANTHROPIC_API_KEY)

    def get_pipeline_steps(self) -> list[dict]:
        """Return the list of pipeline steps for progress tracking."""
        return [dict(s) for s in PIPELINE_STEPS]

    async def run(self, issue_key: str, options: dict = None,
                  on_step_start: Optional[Callable] = None,
                  on_step_complete: Optional[Callable] = None,
                  on_live_event: Optional[Callable] = None) -> dict:
        """Run the complete investigation pipeline.

        Args:
            issue_key: Jira issue key to investigate
            options: Investigation options (repo_override, scope, notes)
            on_step_start: Callback when a step starts
            on_step_complete: Callback when a step completes
            on_live_event: Callback for live feed events

        Returns:
            Complete investigation result dict
        """
        options = options or {}
        scope = options.get("scope", {})
        repo = options.get("repo_override", "web-app")

        result = {
            "bug_snapshot": None,
            "related_issues": [],
            "confluence_docs": [],
            "code_candidates": [],
            "suspicious_commits": [],
            "intent_result": None,
            "recommendation": None,
            "report": None,
            "live_events": [],
        }

        async def emit(msg: str):
            result["live_events"].append(msg)
            if on_live_event:
                await _safe_call(on_live_event, msg)

        async def step_start(n: int):
            if on_step_start:
                await _safe_call(on_step_start, n)

        async def step_done(n: int, summary: str):
            if on_step_complete:
                await _safe_call(on_step_complete, n, summary)

        try:
            # Step 1: Fetch Jira issue
            await step_start(1)
            issue_data = await self.issue_provider.get_issue(issue_key)
            bug_snapshot = await self.intake.normalize_bug(issue_data)
            result["bug_snapshot"] = bug_snapshot
            await emit(f"Fetched issue {issue_key}: \"{bug_snapshot.get('title', '')}\"")
            await step_done(1, f"Fetched {issue_key}")

            # Step 2: Fetch related tickets
            await step_start(2)
            if scope.get("search_jira", True):
                related_issues = await self.issue_provider.get_related_issues(issue_key)
                result["related_issues"] = related_issues
                await emit(f"Found {len(related_issues)} related tickets")
                for ri in related_issues[:3]:
                    await emit(f"  Related: {ri.get('key', '?')} - {ri.get('title', '')}")
            await step_done(2, f"Found {len(result['related_issues'])} related tickets")

            # Step 3: Fetch Confluence docs
            await step_start(3)
            confluence_docs = []
            if scope.get("search_confluence", True):
                keywords = self.intake.extract_keywords(bug_snapshot)
                search_terms = [
                    bug_snapshot.get("component", ""),
                    bug_snapshot.get("title", ""),
                ] + keywords[:3]

                for term in search_terms:
                    if term:
                        docs = await self.docs_provider.search_docs(term)
                        for doc in docs:
                            if doc.get("id") not in [d.get("id") for d in confluence_docs]:
                                confluence_docs.append(doc)
                                await emit(f"Found doc: \"{doc.get('title', '')}\"")

                result["confluence_docs"] = confluence_docs
            await step_done(3, f"Retrieved {len(confluence_docs)} docs")

            # Step 4: Search GitHub
            await step_start(4)
            commits = []
            pull_requests = []
            if scope.get("search_github", True):
                keywords = self.intake.extract_keywords(bug_snapshot)
                await emit(f"Searching GitHub repo '{repo}' with keywords: {', '.join(keywords[:5])}")

                # Get recent commits
                days = 180 if scope.get("deep_history") else 30
                commits = await self.code_provider.get_recent_commits(repo, days=days)
                await emit(f"Found {len(commits)} recent commits")

                # Get PRs from commits
                seen_prs = set()
                for commit in commits:
                    pr_num = commit.get("pr_number")
                    if pr_num and pr_num not in seen_prs:
                        seen_prs.add(pr_num)
                        pr = await self.code_provider.get_pull_request(repo, pr_num)
                        pull_requests.append(pr)
                        await emit(f"Found PR #{pr_num}: \"{pr.get('title', '')}\"")

            await step_done(4, f"Found {len(commits)} commits, {len(pull_requests)} PRs")

            # Step 5: Code localization
            await step_start(5)
            keywords = self.intake.extract_keywords(bug_snapshot)
            module_hints = self.intake.extract_module_hints(bug_snapshot)
            await emit(f"Localizing code with {len(keywords)} keywords and {len(module_hints)} module hints")

            code_candidates = await self.localizer.localize(
                bug_snapshot, keywords, module_hints, repo, commits
            )
            result["code_candidates"] = code_candidates

            for cc in code_candidates[:3]:
                await emit(
                    f"Candidate: {cc.get('file_path', '')} → {cc.get('symbol', '?')} "
                    f"(confidence: {int(cc.get('confidence', 0) * 100)}%)"
                )
            await step_done(5, f"Found {len(code_candidates)} candidate locations")

            # Step 6: Intent analysis (LLM-enhanced when available)
            await step_start(6)
            await emit("Analyzing whether behavior is intentional or a regression...")

            # Try LLM-powered analysis first
            llm_result = None
            if self.llm.is_available:
                await emit("Using AI-powered analysis (Claude API)...")
                llm_result = await self.llm.analyze_bug_context(
                    bug_snapshot, code_candidates, confluence_docs,
                    commits, result["related_issues"]
                )

            if llm_result:
                intent_result = {
                    "classification": llm_result.get("classification", "UNCLEAR"),
                    "confidence": llm_result.get("confidence", 0.5),
                    "regression_signals": llm_result.get("evidence", []),
                    "intentional_signals": [],
                    "root_cause": llm_result.get("root_cause", ""),
                    "llm_enhanced": True,
                }
                await emit("AI analysis complete")
            else:
                # Fallback to rule-based heuristics
                intent_result = await self.intent_analyzer.analyze(
                    bug_snapshot, code_candidates, confluence_docs,
                    commits, pull_requests, result["related_issues"]
                )
                intent_result["llm_enhanced"] = False

            result["intent_result"] = intent_result
            await emit(f"Classification: {intent_result['classification']} (confidence: {int(intent_result['confidence'] * 100)}%)")

            for signal in intent_result.get("regression_signals", [])[:2]:
                await emit(f"  Evidence: {signal}")
            for signal in intent_result.get("intentional_signals", [])[:2]:
                await emit(f"  Intentional signal: {signal}")

            await step_done(6, f"Classification: {intent_result['classification']}")

            # Step 7: Regression finding
            await step_start(7)
            suspicious_commits = []
            if intent_result["classification"] != "LIKELY_INTENTIONAL":
                await emit("Searching for suspicious commits...")
                suspicious_commits = await self.regression_finder.find_suspects(
                    code_candidates, commits, pull_requests, bug_snapshot
                )
                result["suspicious_commits"] = suspicious_commits

                for sc in suspicious_commits[:3]:
                    level = sc.get("suspicion_level", "?")
                    await emit(
                        f"  [{level.upper()}] Commit {sc.get('commit_sha', '?')[:7]} "
                        f"by @{sc.get('author', '?')} - PR #{sc.get('pr_number', '?')}"
                    )
            else:
                await emit("Skipping regression search — behavior appears intentional")

            await step_done(7, f"Found {len(suspicious_commits)} suspicious commits")

            # Step 8: Generate report
            await step_start(8)
            await emit("Generating final report...")

            recommendation = await self.recommender.recommend(
                intent_result["classification"],
                intent_result["confidence"],
                code_candidates,
                suspicious_commits,
                bug_snapshot,
                result["related_issues"]
            )
            result["recommendation"] = recommendation

            report = await self.report_gen.generate(
                bug_snapshot, code_candidates, suspicious_commits,
                intent_result, recommendation, result["related_issues"],
                confluence_docs
            )
            result["report"] = report

            await emit(f"Report complete. Recommendation: {recommendation.get('recommendation', 'N/A')}")
            await step_done(8, "Report generated")

            return result

        except Exception as e:
            logger.error(f"Investigation failed for {issue_key}: {str(e)}")
            raise


async def _safe_call(fn, *args):
    """Safely call a callback, handling both sync and async functions."""
    try:
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.warning(f"Callback error: {e}")

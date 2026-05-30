"""LLM-Powered Analysis Engine.
Uses Claude API (Anthropic) for intelligent root cause analysis.
Falls back to rule-based heuristics when API key is not available.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import anthropic, but don't fail if not installed
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class LLMAnalyzer:
    """LLM-powered analysis for root cause investigation.

    Provides intelligent analysis of bugs, logs, and code by leveraging
    Claude API. Gracefully degrades to None responses when API is unavailable.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.client = None

        if api_key and HAS_ANTHROPIC:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
                logger.info("LLM analyzer initialized with Claude API")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")
        else:
            if not api_key:
                logger.info("LLM analyzer: no API key, using rule-based fallback")
            if not HAS_ANTHROPIC:
                logger.info("LLM analyzer: anthropic package not installed")

    @property
    def is_available(self) -> bool:
        return self.client is not None

    async def analyze_bug_context(self, bug_snapshot: dict, code_candidates: list[dict],
                                    confluence_docs: list[dict], commits: list[dict],
                                    related_issues: list[dict]) -> Optional[dict]:
        """Use LLM to analyze the full bug context and produce intelligent classification.

        Returns None if LLM is not available (caller should use rule-based fallback).
        """
        if not self.is_available:
            return None

        prompt = self._build_bug_analysis_prompt(
            bug_snapshot, code_candidates, confluence_docs, commits, related_issues
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                system="You are a senior software engineer performing root cause analysis on a bug. "
                       "Analyze all evidence and provide a structured assessment. "
                       "Be specific, cite evidence, and give actionable recommendations."
            )

            text = response.content[0].text
            return self._parse_bug_analysis(text)

        except Exception as e:
            logger.error(f"LLM bug analysis failed: {e}")
            return None

    async def analyze_logs(self, raw_logs: str, structured_analysis: dict) -> Optional[dict]:
        """Use LLM to provide intelligent log/stack trace analysis.

        Takes both the raw logs and the structured regex-based analysis
        to produce a more insightful root cause assessment.
        """
        if not self.is_available:
            return None

        prompt = self._build_log_analysis_prompt(raw_logs, structured_analysis)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
                system="You are a senior SRE/DevOps engineer analyzing production logs and stack traces. "
                       "Identify the root cause, explain the error chain, and suggest specific fixes."
            )

            text = response.content[0].text
            return {
                "llm_summary": text,
                "enhanced": True,
            }

        except Exception as e:
            logger.error(f"LLM log analysis failed: {e}")
            return None

    async def generate_executive_summary(self, bug_snapshot: dict, classification: str,
                                          confidence: float, code_candidates: list[dict],
                                          suspicious_commits: list[dict],
                                          recommendation: dict) -> Optional[str]:
        """Use LLM to generate a polished executive summary for the report."""
        if not self.is_available:
            return None

        prompt = f"""Generate a concise executive summary (3-5 sentences) for this bug investigation:

Bug: {bug_snapshot.get('title', 'Unknown')}
Description: {bug_snapshot.get('description', 'N/A')[:300]}
Expected: {bug_snapshot.get('expected_behavior', 'N/A')[:200]}
Actual: {bug_snapshot.get('actual_behavior', 'N/A')[:200]}

Classification: {classification} (Confidence: {int(confidence * 100)}%)

Top Code Location: {code_candidates[0].get('file_path', 'unknown') if code_candidates else 'none found'} → {code_candidates[0].get('symbol', '?') if code_candidates else '?'}

Suspicious Commit: {suspicious_commits[0].get('commit_sha', 'none')[:7] if suspicious_commits else 'none'} by @{suspicious_commits[0].get('author', '?') if suspicious_commits else '?'} — PR #{suspicious_commits[0].get('pr_number', '?') if suspicious_commits else '?'}

Recommendation: {recommendation.get('recommendation', 'N/A')}

Write a clear, professional summary that a developer can quickly scan. Reference specific files, commits, and PRs by name."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return None

    async def suggest_fix(self, bug_snapshot: dict, code_snippet: str,
                           symbol: str, file_path: str) -> Optional[str]:
        """Use LLM to suggest a specific code fix direction."""
        if not self.is_available:
            return None

        prompt = f"""Given this bug and code, suggest a specific fix direction.

Bug: {bug_snapshot.get('title', '')}
Expected: {bug_snapshot.get('expected_behavior', '')}
Actual: {bug_snapshot.get('actual_behavior', '')}

File: {file_path}
Function: {symbol}
Code:
```
{code_snippet[:1500]}
```

Provide:
1. What's wrong (1 sentence)
2. The specific fix (show before/after code change)
3. What test to add (1 sentence)

Be concise and specific."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM fix suggestion failed: {e}")
            return None

    def _build_bug_analysis_prompt(self, bug: dict, code: list, docs: list,
                                     commits: list, related: list) -> str:
        """Build the full analysis prompt for bug investigation."""
        sections = []

        sections.append(f"""## Bug Report
Title: {bug.get('title', 'Unknown')}
Description: {bug.get('description', 'N/A')[:500]}
Expected Behavior: {bug.get('expected_behavior', 'N/A')[:300]}
Actual Behavior: {bug.get('actual_behavior', 'N/A')[:300]}
Component: {bug.get('component', 'unknown')}
Priority: {bug.get('priority', 'unknown')}""")

        if code:
            code_section = "## Code Candidates\n"
            for c in code[:3]:
                code_section += f"- {c.get('file_path', '?')} → {c.get('symbol', '?')} (confidence: {c.get('confidence', 0):.0%})\n"
                snippet = c.get('code_snippet', '')
                if snippet:
                    code_section += f"```\n{snippet[:500]}\n```\n"
            sections.append(code_section)

        if docs:
            doc_section = "## Documentation Found\n"
            for d in docs[:3]:
                doc_section += f"- {d.get('title', '?')}: {d.get('key_excerpt', d.get('content_summary', ''))[:200]}\n"
                doc_section += f"  Relevance: {d.get('relevance_tag', 'unknown')}\n"
            sections.append(doc_section)

        if commits:
            commit_section = "## Recent Commits\n"
            for c in commits[:5]:
                commit_section += f"- {c.get('sha', c.get('commit_sha', '?'))[:7]} by @{c.get('author', '?')}: {c.get('message', c.get('commit_message', ''))[:100]}\n"
                if c.get('pr_number'):
                    commit_section += f"  PR #{c['pr_number']}: {c.get('pr_title', '')}\n"
            sections.append(commit_section)

        if related:
            related_section = "## Related Jira Tickets\n"
            for r in related[:4]:
                related_section += f"- {r.get('key', '?')}: {r.get('title', '?')} (status: {r.get('status', '?')}, relation: {r.get('relation_type', '?')})\n"
            sections.append(related_section)

        sections.append("""## Your Task
Based on ALL evidence above, determine:
1. CLASSIFICATION: Is this LIKELY_REGRESSION, LIKELY_INTENTIONAL, or UNCLEAR?
2. CONFIDENCE: 0.0 to 1.0
3. ROOT_CAUSE: One sentence explaining the most likely root cause
4. EVIDENCE: List the 2-3 strongest pieces of evidence
5. RECOMMENDATION: What should happen next?

Format your response exactly as:
CLASSIFICATION: <value>
CONFIDENCE: <value>
ROOT_CAUSE: <text>
EVIDENCE:
- <evidence 1>
- <evidence 2>
RECOMMENDATION: <text>""")

        return "\n\n".join(sections)

    def _build_log_analysis_prompt(self, raw_logs: str, analysis: dict) -> str:
        """Build prompt for log analysis."""
        return f"""Analyze these logs/stack traces and provide root cause analysis.

## Raw Input
```
{raw_logs[:3000]}
```

## Automated Analysis Results
- Input type: {analysis.get('input_type', 'unknown')}
- Errors found: {len(analysis.get('errors', []))}
- Stack frames: {len(analysis.get('stack_frames', []))}
- Severity: {analysis.get('severity', 'unknown')}
- Key files: {', '.join(f.get('file', '?') for f in analysis.get('key_files', [])[:3])}

## Your Task
1. Explain what happened (root cause chain)
2. Why it happened (underlying reason)
3. How to fix it (specific actionable steps)
4. How to prevent it (preventive measures)

Be concise and specific. Reference line numbers and file names from the stack trace."""

    def _parse_bug_analysis(self, text: str) -> dict:
        """Parse structured LLM response into a dict."""
        result = {
            "classification": "UNCLEAR",
            "confidence": 0.5,
            "root_cause": "",
            "evidence": [],
            "recommendation": "",
            "raw_response": text,
        }

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("CLASSIFICATION:"):
                val = line.split(":", 1)[1].strip().upper()
                if val in ("LIKELY_REGRESSION", "LIKELY_INTENTIONAL", "UNCLEAR", "NEEDS_MORE_DATA"):
                    result["classification"] = val
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("ROOT_CAUSE:"):
                result["root_cause"] = line.split(":", 1)[1].strip()
            elif line.startswith("RECOMMENDATION:"):
                result["recommendation"] = line.split(":", 1)[1].strip()
            elif line.startswith("- ") and result.get("root_cause"):
                result["evidence"].append(line[2:].strip())

        return result

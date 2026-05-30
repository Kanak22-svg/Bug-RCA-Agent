"""Log & Stack Trace Analysis API endpoints."""
from fastapi import APIRouter
from app.models.schemas import AnalyzeLogsRequest, LogAnalysisResponse
from app.engine.log_analyzer import LogAnalyzer
from app.engine.llm_analyzer import LLMAnalyzer
from app.config import settings

router = APIRouter(prefix="/analyze", tags=["analysis"])

analyzer = LogAnalyzer()
llm = LLMAnalyzer(api_key=settings.ANTHROPIC_API_KEY)


@router.post("/logs", response_model=LogAnalysisResponse)
async def analyze_logs(request: AnalyzeLogsRequest):
    """Analyze raw logs, stack traces, or error messages for root cause signals.

    Accepts raw text input (logs, stack traces, error output) and returns
    structured analysis with error extraction, stack frame parsing,
    severity classification, and root cause hints.

    When ANTHROPIC_API_KEY is configured, provides LLM-enhanced analysis.
    """
    result = await analyzer.analyze(request.raw_input)

    # Enhance with LLM if available
    if llm.is_available:
        llm_result = await llm.analyze_logs(request.raw_input, result)
        if llm_result:
            result["root_cause_hints"].insert(0, llm_result.get("llm_summary", "")[:500])

    return LogAnalysisResponse(**result)


@router.post("/stacktrace", response_model=LogAnalysisResponse)
async def analyze_stacktrace(request: AnalyzeLogsRequest):
    """Alias for /logs — specifically for stack trace input."""
    return await analyze_logs(request)

"""Route questions through Groq with a reliable local-data fallback."""

from typing import Any, Callable

from graph.workflow import run_nexus_workflow
from utils.local_analytics import run_local_analysis


def run_business_analysis(
    question: str,
    use_provider: bool,
    trigger_flow: bool = False,
    progress_callback: Callable[[str, dict], None] | None = None,
) -> dict[str, Any]:
    """Return Groq results when available, otherwise a labeled local answer."""
    if not use_provider:
        result = run_local_analysis(question)
        result["mode"] = "Local demo analytics"
        result["fallback_notice"] = (
            "GROQ_API_KEY is not configured. This answer uses the included "
            "sample database; verify it against current business systems."
        )
        return result

    failure = None
    try:
        result = dict(
            run_nexus_workflow(
                question,
                trigger_flow=trigger_flow,
                progress_callback=progress_callback,
            )
        )
        if not result.get("error") and result.get("final_recommendation"):
            result["mode"] = "Groq multi-agent workflow"
            return result
        failure = result.get("error") or "Groq returned no recommendation."
    except Exception as error:
        failure = error

    result = run_local_analysis(question)
    result["mode"] = "Local fallback analytics"
    result["fallback_notice"] = _fallback_notice(str(failure))
    return result


def _fallback_notice(error: str) -> str:
    normalized = error.casefold()
    if "401" in normalized or "403" in normalized or "api key" in normalized:
        reason = "Groq rejected the configured key or permissions"
    elif "429" in normalized or "resource_exhausted" in normalized:
        reason = "Groq quota or rate limit was reached"
    elif any(code in normalized for code in ("500", "502", "503", "504", "unavailable")):
        reason = "Groq is temporarily unavailable"
    elif "timeout" in normalized or "timed out" in normalized:
        reason = "Groq did not respond before the timeout"
    else:
        reason = "Groq could not complete the request"
    return (
        f"{reason}. This answer uses the included sample database; verify it "
        "against current business systems before acting."
    )
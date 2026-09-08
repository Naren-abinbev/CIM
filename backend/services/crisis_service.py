from datetime import datetime
from math import ceil

from backend.ai.llm.llm import AzureLLMConfigurationError, get_azure_llm
from backend.ai.prompts.crisis import CRISIS_ANALYSIS_PROMPT
from backend.schemas.crisis import CrisisAnalysisResponse


mock_crises = [

    {
        "id": "CR-10001",

        "title": (
            "Pricing Engine outage impacting "
            "order pricing in Mexico and Central America"
        ),

        "severity": "SEV1",

        "businessImpact": "18.4K orders blocked",

        "status": "IDENTIFIED",

        "service": "pricing-engine-prod",

        "zone": "MAZ",

        "age": {
            "value": 34,
            "unit": "MINUTES"
        },

        "commander": {
            "id": "USR-101",
            "name": "Maria Santos"
        },

        "createdAt": datetime.fromisoformat(
            "2026-09-03T10:30:00+00:00"
        ),

        "updatedAt": datetime.fromisoformat(
            "2026-09-03T11:04:00+00:00"
        )
    }
]


def get_crises(
    page: int = 1,
    page_size: int = 20,
    severity: str | None = None,
    status: str | None = None,
    zone: str | None = None,
    service: str | None = None,
):
    filtered_crises = [
        crisis
        for crisis in mock_crises
        if (severity is None or crisis["severity"] == severity)
        and (status is None or crisis["status"] == status)
        and (zone is None or crisis["zone"] == zone)
        and (service is None or crisis["service"] == service)
    ]
    total_items = len(filtered_crises)
    start = (page - 1) * page_size
    page_data = filtered_crises[start : start + page_size]
    total_pages = ceil(total_items / page_size) if total_items else 0

    return {
        "data": page_data,
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "totalItems": total_items,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1 and total_items > 0,
        },
    }


async def analyze_crisis(
    report: str,
    crisis_type: str | None = None,
    top_k: int = 3,
) -> CrisisAnalysisResponse:
    prompt = CRISIS_ANALYSIS_PROMPT.format(
        crisis_type=crisis_type or "Not specified",
        top_k=top_k,
        report=report,
    )
    try:
        response = await get_azure_llm().with_structured_output(
            CrisisAnalysisResponse
        ).ainvoke(prompt)
    except AzureLLMConfigurationError:
        raise
    except Exception as exc:
        raise RuntimeError("Crisis analysis failed.") from exc
    return response
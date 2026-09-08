from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.ai.llm.llm import AzureLLMConfigurationError
from backend.schemas.crisis import (
    CrisisAnalysisRequest,
    CrisisAnalysisResponse,
    CrisisListResponse,
)

from backend.services.crisis_service import analyze_crisis, get_crises


router = APIRouter(

    prefix="/crises",

    tags=["Crises"]
)


@router.post(
    "/analyze",
    response_model=CrisisAnalysisResponse,
)
async def analyze_crisis_report(
    request: CrisisAnalysisRequest,
) -> CrisisAnalysisResponse:
    if not request.report.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="report must contain text",
        )
    try:
        return await analyze_crisis(
            report=request.report.strip(),
            crisis_type=request.crisis_type,
            top_k=request.top_k,
        )
    except AzureLLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crisis analysis is not configured.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Crisis analysis failed.",
        ) from exc


@router.get(

    "",

    response_model=CrisisListResponse
)
async def get_crisis_list(

    page: int = Query(
        1,
        ge=1
    ),

    pageSize: int = Query(
        20,
        ge=1,
        le=100
    ),

    severity: Optional[str] = None,

    status: Optional[str] = None,

    zone: Optional[str] = None,

    service: Optional[str] = None

):

    return get_crises(

        page=page,

        page_size=pageSize,

        severity=severity,

        status=status,

        zone=zone,

        service=service
    )
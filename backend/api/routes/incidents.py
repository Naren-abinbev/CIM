from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable
from typing import Annotated
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser
from backend.core.config import Settings, get_settings
from backend.database.database import get_db
from backend.services import incident_service
from backend.schemas.incident import IncidentCreate, IncidentResponse
from backend.rag.servicenow_incident_ingestion import (
    GeminiEmbeddingClient,
    GeminiEmbeddingError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/incidents", tags=["Incident Search"])
SEARCH_CANDIDATE_COUNT = 10
TOP_K = 3
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
FILTER_FIELDS = {"incnumber", "link", "created", "closed", "severity", "priority", "correlation_id"}


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Incidents"],
)
def create_incident(
    payload: IncidentCreate,
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> IncidentResponse:
    """Create an incident in SQLite for the authenticated user."""
    try:
        incident = incident_service.create_incident(
            db,
            payload=payload,
            user_email=user.email,
            user_id=user.id,
        )
        db.commit()
        db.refresh(incident)
        return IncidentResponse.model_validate(incident)
    except incident_service.IncidentAlreadyExistsError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "INCIDENT_ALREADY_EXISTS",
                    "message": str(exc),
                }
            },
        ) from exc


@router.get(
    "/by-number/{incident_number}",
    response_model=IncidentResponse,
    tags=["Incidents"],
)
def get_incident_by_number(
    incident_number: str,
    db: Annotated[Session, Depends(get_db)],
    _user: CurrentUser,
) -> IncidentResponse:
    """Read an incident by its incident number."""
    try:
        incident = incident_service.get_incident_by_number(
            db,
            incident_number=incident_number,
        )
        return IncidentResponse.model_validate(incident)
    except incident_service.IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "INCIDENT_NOT_FOUND",
                    "message": str(exc),
                }
            },
        ) from exc


class IncidentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    incnumber: str | None = None
    link: str | None = None
    created: str | None = None
    closed: str | None = None
    severity: str | None = None
    priority: str | None = None
    correlation_id: str | None = None


class IncidentSearchRequest(BaseModel):
    short_description: str | None = None
    description: str | None = None
    metadata: IncidentMetadata | None = None

    @field_validator("short_description", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

class SearchResult(BaseModel):
    id: str
    score: float
    text: str
    content: str
    metadata: dict[str, Any]


class IncidentSearchResponse(BaseModel):
    vector_store: str
    total_results: int
    results: list[SearchResult]


def _meaningful_metadata(metadata: IncidentMetadata | None) -> dict[str, str]:
    if metadata is None:
        return {}
    return {
        key: value.strip()
        for key, value in metadata.model_dump().items()
        if key in FILTER_FIELDS and isinstance(value, str) and value.strip()
    }


def _build_search_text(request: IncidentSearchRequest) -> str:
    parts: list[str] = []
    if request.short_description:
        parts.extend(["Short Description:", request.short_description])
    if request.description:
        parts.extend(["Description:", request.description])
    return "\n\n".join(parts)


def _build_odata_filter(metadata: dict[str, str]) -> str | None:
    clauses = [
        f"{field} eq '{value.replace(chr(39), chr(39) * 2)}'"
        for field, value in metadata.items()
        if field in FILTER_FIELDS and value
    ]
    return " and ".join(clauses) if clauses else None


def _build_chroma_filter(metadata: dict[str, str]) -> dict[str, Any] | None:
    conditions = [{field: value} for field, value in metadata.items() if value]
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def _azure_configured(settings: Settings) -> bool:
    return settings.azure_search_available


def _azure_client(settings: Settings) -> Any:
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
    except ImportError as exc:
        raise RuntimeError("azure-search-documents is required for configured Azure AI Search.") from exc
    return SearchClient(
        endpoint=settings.azure_search_endpoint.rstrip("/"),
        index_name=settings.azure_search_index_name,
        credential=AzureKeyCredential(settings.azure_search_api_key),
    )


def _normalize_azure_result(item: dict[str, Any]) -> SearchResult:
    metadata = {field: item.get(field, "") for field in FILTER_FIELDS if item.get(field) is not None}
    raw_score = item.get("@search.reranker_score", item.get("@search.score", 0.0))
    score = float(raw_score or 0.0)
    if item.get("@search.reranker_score") is not None:
        score /= 4.0
    score = max(0.0, min(score, 1.0))
    return SearchResult(
        id=str(item.get("id") or item.get("incnumber") or ""),
        score=score,
        text=str(item.get("content") or ""),
        content=str(item.get("content") or ""),
        metadata=metadata,
    )


async def _azure_hybrid_search(settings: Settings, search_text: str, embedding: list[float], metadata: dict[str, str]) -> list[SearchResult]:
    from azure.search.documents.models import VectorizedQuery

    client = _azure_client(settings)
    logger.info("Applying metadata filtering and executing Azure hybrid search.")
    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=SEARCH_CANDIDATE_COUNT,
        fields="content_vector",
    )

    def execute() -> list[SearchResult]:
        results = client.search(
            search_text=search_text,
            search_fields=["content"],
            vector_queries=[vector_query],
            filter=_build_odata_filter(metadata),
            select=["id", "content", "incnumber", "link", "created", "closed", "severity", "priority", "correlation_id"],
            top=SEARCH_CANDIDATE_COUNT,
            query_type="semantic",
            semantic_configuration_name="default",
        )
        return [_normalize_azure_result(item) for item in results]

    results = await asyncio.to_thread(execute)
    logger.info("Retrieved %s Azure AI Search candidates.", len(results))
    return [
        result
        for result in results
        if result.score > settings.search_min_relevance_score
    ][:TOP_K]


def _get_chroma_collection(settings: Settings) -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required for local fallback search.") from exc
    return chromadb.PersistentClient(path=settings.chroma_persist_directory).get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def _keyword_score(query_text: str, content: str) -> float:
    query_terms = set(re.findall(r"[a-z0-9]+", query_text.lower()))
    content_terms = set(re.findall(r"[a-z0-9]+", content.lower()))
    return len(query_terms & content_terms) / len(query_terms) if query_terms else 0.0


def _rerank_chroma_results(query_text: str, documents: Iterable[str], ids: Iterable[str], metadatas: Iterable[dict[str, Any]], distances: Iterable[float]) -> list[SearchResult]:
    ranked: list[SearchResult] = []
    for incident_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
        vector_score = max(0.0, 1.0 - float(distance))
        score = vector_score * VECTOR_WEIGHT + _keyword_score(query_text, content) * KEYWORD_WEIGHT
        ranked.append(
            SearchResult(
                id=str(incident_id),
                score=score,
                text=content,
                content=content,
                metadata=metadata or {},
            )
        )
    ranked.sort(key=lambda result: result.score, reverse=True)
    return ranked[:TOP_K]


async def _chroma_search(settings: Settings, search_text: str, embedding: list[float], metadata: dict[str, str]) -> list[SearchResult]:
    collection = await asyncio.to_thread(_get_chroma_collection, settings)
    logger.info("Applying metadata filtering and executing ChromaDB vector search.")

    def execute() -> dict[str, Any]:
        return collection.query(
            query_embeddings=[embedding],
            n_results=SEARCH_CANDIDATE_COUNT,
            where=_build_chroma_filter(metadata),
            include=["documents", "metadatas", "distances"],
        )

    payload = await asyncio.to_thread(execute)
    documents = payload.get("documents", [[]])[0] or []
    ids = payload.get("ids", [[]])[0] or []
    metadatas = payload.get("metadatas", [[]])[0] or []
    distances = payload.get("distances", [[]])[0] or []
    results = [
        result
        for result in _rerank_chroma_results(
            search_text,
            documents,
            ids,
            metadatas,
            distances,
        )
        if result.score > settings.search_min_relevance_score
    ][:TOP_K]
    logger.info("Retrieved %s ChromaDB candidates after keyword reranking.", len(results))
    return results


async def _search(request: IncidentSearchRequest) -> IncidentSearchResponse:
    settings = get_settings()
    search_text = _build_search_text(request)
    metadata = _meaningful_metadata(request.metadata)
    logger.info("Incident search request received. Generating Gemini embedding.")
    try:
        embedding = await GeminiEmbeddingClient(settings).generate_embedding(search_text)
    except GeminiEmbeddingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"error": {"code": "EMBEDDING_FAILED", "message": str(exc)}}) from exc

    if _azure_configured(settings):
        logger.info("Using Azure AI Search.")
        try:
            results = await _azure_hybrid_search(settings, search_text, embedding, metadata)
        except Exception as exc:
            logger.exception("Azure AI Search failed while configured.")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"error": {"code": "AZURE_SEARCH_FAILED", "message": "Azure AI Search is unavailable."}}) from exc
        vector_store = "azure_ai_search"
    else:
        logger.info("Azure AI Search is not configured. Using ChromaDB fallback.")
        try:
            results = await _chroma_search(settings, search_text, embedding, metadata)
        except Exception as exc:
            logger.exception("ChromaDB search failed.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": {"code": "CHROMA_SEARCH_FAILED", "message": "ChromaDB search failed."}}) from exc
        vector_store = "chroma"

    logger.info("Returning top 3 results. Search completed successfully.")
    return IncidentSearchResponse(vector_store=vector_store, total_results=len(results), results=results)


@router.post("/search", response_model=IncidentSearchResponse)
async def search_incidents(request: IncidentSearchRequest) -> IncidentSearchResponse:
    if not any(value for value in (request.short_description, request.description)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SEARCH", "message": "short_description or description must contain text"}},
        )
    try:
        return await _search(request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected incident search failure.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error": {"code": "SEARCH_FAILED", "message": "Incident search failed."}}) from exc

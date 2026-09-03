from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Sequence
from pathlib import Path

import httpx

# Allow direct execution as `python backend/rag/servicenow_incident_ingestion.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import Settings

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    genai_types = None

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchField,
        SearchIndex,
        SimpleField,
        SearchableField,
        VectorSearch,
        VectorSearchAlgorithmConfiguration,
        VectorSearchProfile,
    )
except ImportError:  # pragma: no cover - optional dependency
    AzureKeyCredential = None
    SearchClient = None
    SearchIndexClient = None
    SearchField = None
    SearchIndex = None
    SimpleField = None
    SearchableField = None
    VectorSearch = None
    VectorSearchAlgorithmConfiguration = None
    VectorSearchProfile = None

try:
    import chromadb
except ImportError:  # pragma: no cover - optional dependency
    chromadb = None


logger = logging.getLogger("servicenow_incident_ingestion")


def _is_placeholder(value: str | None) -> bool:
    """Return True when an environment value still contains a template placeholder."""
    if value is None:
        return True
    cleaned = value.strip()
    if not cleaned:
        return True
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return True
    if "your-" in cleaned.lower() or "example" in cleaned.lower():
        return True
    return False


def configure_logging() -> None:
    """Configure application logging for the ingestion module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@dataclass(slots=True)
class IncidentDocument:
    """Prepared document representation for vector ingestion."""

    id: str
    content: str
    metadata: dict[str, str]
    embedding: list[float] | None = None


class ServiceNowError(RuntimeError):
    """Base ServiceNow ingestion exception."""


class ServiceNowFetchError(ServiceNowError):
    """Raised when a ServiceNow fetch fails."""


class ServiceNowAuthenticationError(ServiceNowError):
    """Raised when ServiceNow authentication fails."""


class ServiceNowResponseError(ServiceNowError):
    """Raised when ServiceNow returns an invalid or failed response."""


class ServiceNowClient:
    """Async client for retrieving ServiceNow incident records."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.instance_url = settings.servicenow_instance_url.rstrip("/")
        self.username = settings.servicenow_username
        self.password = settings.servicenow_password
        self.client_id = settings.servicenow_client_id
        self.client_secret = settings.servicenow_client_secret
        self.page_size = max(1, int(settings.servicenow_page_size))
        self.timeout = float(settings.http_timeout)

        if not self.instance_url:
            raise ServiceNowAuthenticationError(
                "SERVICENOW_INSTANCE_URL is not configured."
            )
        if not self.username or not self.password:
            raise ServiceNowAuthenticationError(
                "SERVICENOW_USERNAME and SERVICENOW_PASSWORD must be configured."
            )

        self.oauth_url = f"{self.instance_url}/oauth_token.do"
        self.base_url = f"{self.instance_url}/api/now/table/incident"
        self._access_token: str | None = None

    async def _get_access_token(self) -> str:
        """Acquire an OAuth access token using the ServiceNow password-grant flow."""
        if self._access_token:
            return self._access_token

        if not self.client_id or not self.client_secret:
            logger.warning(
                "ServiceNow OAuth client credentials are not configured. Falling back to username/password auth."
            )
            return ""

        payload = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.post(
                    self.oauth_url,
                    data=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("ServiceNow OAuth token request failed.")
            raise ServiceNowAuthenticationError(
                "Unable to connect to the ServiceNow OAuth endpoint."
            ) from exc

        if response.status_code != 200:
            logger.error(
                "ServiceNow OAuth failed with HTTP %s: %s",
                response.status_code,
                response.text[:500],
            )
            raise ServiceNowAuthenticationError(
                "ServiceNow OAuth authentication failed. Check client_id and secret."
            )

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("ServiceNow OAuth response was not valid JSON.")
            raise ServiceNowAuthenticationError(
                "ServiceNow OAuth response was not valid JSON."
            ) from exc

        self._access_token = data.get("access_token")
        if not self._access_token:
            raise ServiceNowAuthenticationError(
                "ServiceNow OAuth response did not contain an access token."
            )

        logger.info("ServiceNow OAuth token acquired successfully.")
        return self._access_token

    def _safe_params(self, *, offset: int, page_size: int) -> dict[str, Any]:
        return {
            "sysparm_limit": page_size,
            "sysparm_offset": offset,
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": (
                "number,sys_id,sys_created_on,closed_at,severity,priority,"
                "correlation_id,short_description,description"
            ),
        }

    async def fetch_incidents(
        self,
        *,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all incident records from the ServiceNow incident table."""
        effective_page_size = page_size or self.page_size
        all_incidents: list[dict[str, Any]] = []
        offset = 0
        page_count = 0

        logger.info("Fetching incidents from ServiceNow.")

        access_token = await self._get_access_token()
        headers = {
            "Accept": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            logger.warning("Using fallback username/password auth for ServiceNow request.")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        ) as client:
            while True:
                page_count += 1
                if max_pages and page_count > max_pages:
                    logger.warning(
                        "Reached max ServiceNow page limit (%s). Stopping pagination.",
                        max_pages,
                    )
                    break

                params = self._safe_params(
                    offset=offset,
                    page_size=effective_page_size,
                )
                try:
                    response = await client.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                    )
                except httpx.TimeoutException as exc:
                    logger.error("ServiceNow request timed out while fetching incidents.")
                    raise ServiceNowFetchError(
                        "ServiceNow request timed out while fetching incidents."
                    ) from exc
                except httpx.HTTPError as exc:
                    logger.error(
                        "ServiceNow request failed while fetching incidents: %s",
                        exc,
                    )
                    raise ServiceNowFetchError(
                        "ServiceNow request failed while fetching incidents."
                    ) from exc

                if response.status_code == 401:
                    logger.error("ServiceNow authentication failed for incident fetch.")
                    raise ServiceNowAuthenticationError(
                        "ServiceNow authentication failed. Check credentials."
                    )
                if response.status_code >= 400:
                    logger.error(
                        "ServiceNow fetch failed with status %s: %s",
                        response.status_code,
                        response.text[:500],
                    )
                    raise ServiceNowResponseError(
                        f"ServiceNow API error: HTTP {response.status_code}"
                    )

                try:
                    payload = response.json()
                except ValueError as exc:
                    logger.error("ServiceNow response was not valid JSON.")
                    raise ServiceNowResponseError(
                        "ServiceNow response was not valid JSON."
                    ) from exc

                records = payload.get("result", [])
                if not isinstance(records, list):
                    logger.error(
                        "ServiceNow returned an unexpected payload format: %s",
                        payload,
                    )
                    raise ServiceNowResponseError(
                        "ServiceNow returned an unexpected result payload."
                    )

                if not records:
                    logger.info("No more ServiceNow incidents found.")
                    break

                all_incidents.extend(records)
                logger.info(
                    "Fetched %s incidents from ServiceNow page %s.",
                    len(records),
                    page_count,
                )

                if len(records) < effective_page_size:
                    logger.info("Reached the end of ServiceNow incident pagination.")
                    break

                offset += len(records)

        logger.info("Fetched %s incidents from ServiceNow.", len(all_incidents))
        return all_incidents


class GeminiEmbeddingError(RuntimeError):
    """Raised when Gemini embedding generation fails."""


class GeminiEmbeddingClient:
    """Gemini embedding service used for incident vectorization."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.gemini_api_key.strip()
        self.model = settings.gemini_embedding_model or "gemini-embedding-001"

        if not self.api_key:
            raise GeminiEmbeddingError("GEMINI_API_KEY is not configured.")

        if genai is None:
            raise GeminiEmbeddingError(
                "google-genai is required. Install it with: pip install google-genai"
            )

        self.client = genai.Client(api_key=self.api_key)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate and return a Gemini embedding for the provided text."""
        if not text or not text.strip():
            raise GeminiEmbeddingError("Cannot generate an embedding for empty text.")

        try:
            if genai_types is not None:
                config = genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                )
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=text,
                    config=config,
                )
            else:
                result = self.client.models.embed_content(
                    model=self.model,
                    contents=text,
                )

            embedding_values = getattr(result, "embeddings", None)
            if not embedding_values:
                raise GeminiEmbeddingError("Gemini returned no embeddings.")

            embedding = embedding_values[0].values
            if not embedding:
                raise GeminiEmbeddingError("Gemini returned an empty embedding.")

            normalized = [float(value) for value in embedding]
            logger.info(
                "Generated Gemini embedding for text with %s dimensions.",
                len(normalized),
            )
            return normalized

        except GeminiEmbeddingError:
            raise
        except Exception as exc:  # pragma: no cover - API library behavior varies
            logger.exception("Gemini embedding generation failed.")
            raise GeminiEmbeddingError(
                "Failed to generate Gemini embedding for incident text."
            ) from exc


class BaseVectorStore(ABC):
    """Abstraction for vector storage backends."""

    @abstractmethod
    async def upsert_documents(
        self,
        documents: Sequence[IncidentDocument],
    ) -> int:
        """Insert or update incident documents into the configured vector store."""


def _normalize_metadata_value(value: Any) -> str:
    """Convert metadata values into a database-safe string."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)
    return str(value)


class AzureAISearchVectorStore(BaseVectorStore):
    """Azure AI Search-powered vector store with automatic index management."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        if AzureKeyCredential is None or SearchIndexClient is None:
            raise RuntimeError(
                "azure-search-documents is required. Install it with: pip install azure-search-documents"
            )

        self.endpoint = settings.azure_search_endpoint.rstrip("/")
        self.api_key = settings.azure_search_api_key
        self.index_name = settings.azure_search_index_name
        logger.info(
            "Azure AI Search configuration: endpoint=%s index=%s",
            self.endpoint,
            self.index_name,
        )
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key),
        )
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.api_key),
        )

    def _vector_dimensions(self, documents: Sequence[IncidentDocument]) -> int:
        for document in documents:
            if document.embedding is not None:
                return len(document.embedding)
        raise ValueError("No embeddings were provided for Azure AI Search indexing.")

    def _index_exists(self) -> bool:
        try:
            self.index_client.get_index(self.index_name)
            return True
        except Exception:
            return False

    def _build_index(self, vector_dimensions: int) -> SearchIndex:
        vector_search = VectorSearch(
            algorithms=[
                VectorSearchAlgorithmConfiguration(
                    name="default-vector-config",
                    kind="hnsw",
                    hnsw_parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="default-vector-profile",
                    algorithm_configuration_name="default-vector-config",
                )
            ],
        )

        fields = [
            SimpleField(name="id", type="Edm.String", key=True, filterable=True),
            SearchableField(name="content", type="Edm.String", searchable=True),
            SearchField(
                name="content_vector",
                type="Collection(Edm.Single)",
                searchable=True,
                vector_search_dimensions=vector_dimensions,
                vector_search_profile_name="default-vector-profile",
            ),
            SimpleField(name="incnumber", type="Edm.String", filterable=True),
            SimpleField(name="link", type="Edm.String", filterable=True),
            SimpleField(name="created", type="Edm.String", filterable=True),
            SimpleField(name="closed", type="Edm.String", filterable=True),
            SimpleField(name="severity", type="Edm.String", filterable=True),
            SimpleField(name="priority", type="Edm.String", filterable=True),
            SimpleField(name="correlation_id", type="Edm.String", filterable=True),
        ]

        return SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
        )

    def _ensure_index(self, vector_dimensions: int) -> None:
        if self._index_exists():
            index = self.index_client.get_index(self.index_name)
            vector_field = next(
                (field for field in index.fields if field.name == "content_vector"),
                None,
            )
            if vector_field is None:
                raise ValueError(
                    "Azure AI Search index exists but is missing the required 'content_vector' field."
                )
            if getattr(vector_field, "vector_search_dimensions", None) is not None:
                existing_dimensions = int(vector_field.vector_search_dimensions)
                if existing_dimensions != vector_dimensions:
                    raise ValueError(
                        "Embedding dimension mismatch: Azure AI Search index expects "
                        f"{existing_dimensions} dimensions, but the generated embedding has {vector_dimensions}."
                    )
            return

        logger.info(
            "Azure AI Search index '%s' does not exist. Creating it.",
            self.index_name,
        )
        self.index_client.create_or_update_index(self._build_index(vector_dimensions))

    async def upsert_documents(
        self,
        documents: Sequence[IncidentDocument],
    ) -> int:
        """Insert or update documents in Azure AI Search."""
        if not documents:
            return 0

        vector_dimensions = self._vector_dimensions(documents)
        self._ensure_index(vector_dimensions)

        azure_documents: list[dict[str, Any]] = []
        for document in documents:
            if document.embedding is None:
                raise ValueError(
                    f"Cannot store incident '{document.id}' without an embedding."
                )

            azure_documents.append(
                {
                    "id": document.id,
                    "content": document.content,
                    "content_vector": document.embedding,
                    "incnumber": document.metadata.get("incnumber", ""),
                    "link": document.metadata.get("link", ""),
                    "created": document.metadata.get("created", ""),
                    "closed": document.metadata.get("closed", ""),
                    "severity": document.metadata.get("severity", ""),
                    "priority": document.metadata.get("priority", ""),
                    "correlation_id": document.metadata.get("correlation_id", ""),
                }
            )

        try:
            result = self.search_client.merge_or_upload_documents(azure_documents)
            count = len(result) if result else len(azure_documents)
            logger.info(
                "Stored %s incident(s) in Azure AI Search index '%s'.",
                count,
                self.index_name,
            )
            return count
        except Exception as exc:
            logger.exception(
                "Failed to store incidents in Azure AI Search index '%s'.",
                self.index_name,
            )
            raise RuntimeError(
                "Azure AI Search document upload failed."
            ) from exc


class ChromaVectorStore(BaseVectorStore):
    """Persistent ChromaDB vector store used as a fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if chromadb is None:
            raise RuntimeError(
                "chromadb is required. Install it with: pip install chromadb"
            )

        self.persist_directory = Path(settings.chroma_persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = settings.chroma_collection_name
        logger.info(
            "ChromaDB persistence directory: %s | collection: %s",
            str(self.persist_directory.resolve()),
            self.collection_name,
        )

        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert_documents(
        self,
        documents: Sequence[IncidentDocument],
    ) -> int:
        """Insert or update documents in ChromaDB."""
        if not documents:
            return 0

        ids: list[str] = []
        documents_text: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, str]] = []

        for document in documents:
            if document.embedding is None:
                raise ValueError(
                    f"Cannot store incident '{document.id}' without an embedding."
                )
            ids.append(document.id)
            documents_text.append(document.content)
            embeddings.append(document.embedding)
            metadatas.append(document.metadata)

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents_text,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info(
                "Stored %s incident(s) in ChromaDB collection '%s'.",
                len(documents),
                self.collection_name,
            )
            return len(documents)
        except Exception as exc:
            logger.exception(
                "Failed to store incidents in ChromaDB collection '%s'.",
                self.collection_name,
            )
            raise RuntimeError("ChromaDB upsert failed.") from exc


def get_vector_store(settings: Settings) -> BaseVectorStore:
    """Select the appropriate vector store based on configured credentials."""
    if settings.azure_search_available:
        logger.info("Azure AI Search configuration detected. Using Azure AI Search.")
        return AzureAISearchVectorStore(settings)

    logger.info(
        "Azure AI Search configuration not found. Falling back to ChromaDB."
    )
    return ChromaVectorStore(settings)


class ServiceNowIncidentIngestionService:
    """Orchestrates ServiceNow fetch, conversion, embedding, and storage."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.service_now_client = ServiceNowClient(self.settings)
        self.embedding_client = GeminiEmbeddingClient(self.settings)
        self.vector_store = get_vector_store(self.settings)

    def build_incident_link(self, incident: dict[str, Any]) -> str:
        """Construct a direct ServiceNow incident URL."""
        instance_url = self.settings.servicenow_instance_url.rstrip("/")
        sys_id = incident.get("sys_id")
        if instance_url and sys_id:
            return (
                f"{instance_url}/nav_to.do?uri=incident.do?sys_id={sys_id}"
            )
        if incident.get("link"):
            return str(incident["link"])
        return ""

    def prepare_document(self, incident: dict[str, Any]) -> IncidentDocument | None:
        """Convert a ServiceNow incident into a single vector document."""
        incident_number = str(incident.get("number") or "").strip()
        if not incident_number:
            logger.warning("Skipping incident with missing number: %s", incident)
            return None

        short_description = _normalize_metadata_value(
            incident.get("short_description") or ""
        ).strip()
        description = _normalize_metadata_value(
            incident.get("description") or ""
        ).strip()

        if not short_description and not description:
            logger.warning(
                "Skipping incident %s because short_description and description are empty.",
                incident_number,
            )
            return None

        content_parts: list[str] = []
        if short_description:
            content_parts.append(f"Short Description:\n{short_description}")
        else:
            content_parts.append("Short Description:\n")

        if description:
            content_parts.append(f"\nDescription:\n{description}")
        else:
            content_parts.append("\nDescription:\n")

        document_content = "\n\n".join(content_parts)

        metadata: dict[str, str] = {
            "incnumber": incident_number,
            "link": self.build_incident_link(incident),
            "created": _normalize_metadata_value(incident.get("sys_created_on") or ""),
            "closed": _normalize_metadata_value(incident.get("closed_at") or ""),
            "severity": _normalize_metadata_value(incident.get("severity") or ""),
            "priority": _normalize_metadata_value(incident.get("priority") or ""),
            "correlation_id": _normalize_metadata_value(
                incident.get("correlation_id") or ""
            ),
        }

        logger.info("Processing incident %s.", incident_number)
        return IncidentDocument(
            id=incident_number,
            content=document_content,
            metadata=metadata,
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate and return a Gemini embedding for the incident text."""
        logger.info("Generating Gemini embedding for incident text.")
        return await self.embedding_client.generate_embedding(text)

    async def process_incident(self, incident: dict[str, Any]) -> str:
        """Process one incident into a document, create an embedding, and store it."""
        incident_number = str(incident.get("number") or "").strip()
        if not incident_number:
            logger.warning("Skipping incident missing 'number' field: %s", incident)
            return "skipped"

        try:
            document = self.prepare_document(incident)
            if document is None:
                return "skipped"

            embedding = await self.generate_embedding(document.content)
            document.embedding = embedding

            stored_count = await self.vector_store.upsert_documents([document])
            if stored_count <= 0:
                logger.warning("No documents were stored for incident %s.", incident_number)
                return "failed"

            logger.info("Incident %s successfully stored.", incident_number)
            return "stored"
        except Exception as exc:
            logger.exception("Incident processing failed for %s.", incident_number)
            return "failed"

    async def fetch_incidents(self) -> list[dict[str, Any]]:
        """Fetch incidents from ServiceNow."""
        return await self.service_now_client.fetch_incidents(
            page_size=self.settings.servicenow_page_size,
        )

    async def ingest(self) -> dict[str, Any]:
        """Run the complete asynchronous ingestion workflow."""
        summary: dict[str, Any] = {
            "total_fetched": 0,
            "processed": 0,
            "stored": 0,
            "failed": 0,
            "skipped": 0,
            "vector_store": "unknown",
        }

        logger.info("Starting ServiceNow incident ingestion.")

        try:
            incidents = await self.fetch_incidents()
        except Exception as exc:
            logger.exception("ServiceNow incident fetch failed.")
            summary["vector_store"] = (
                "azure_ai_search"
                if self.settings.azure_search_available
                else "chroma"
            )
            return summary | {"failed": 1, "processed": 0}

        summary["total_fetched"] = len(incidents)
        summary["vector_store"] = (
            "azure_ai_search" if self.settings.azure_search_available else "chroma"
        )

        if not incidents:
            logger.info("No incidents were returned by ServiceNow.")
            logger.info("Ingestion completed.")
            return summary

        semaphore = asyncio.Semaphore(max(1, int(self.settings.ingestion_concurrency)))

        async def run_incident(incident: dict[str, Any]) -> str:
            async with semaphore:
                return await self.process_incident(incident)

        tasks = [asyncio.create_task(run_incident(incident)) for incident in incidents]

        try:
            for task in asyncio.as_completed(tasks):
                status = await task
                if status == "stored":
                    summary["stored"] += 1
                    summary["processed"] += 1
                elif status == "skipped":
                    summary["skipped"] += 1
                    summary["processed"] += 1
                elif status == "failed":
                    summary["failed"] += 1
        except Exception as exc:
            logger.exception("Unexpected error while running ingestion tasks.")
            summary["failed"] += 1

        logger.info("Ingestion completed.")
        logger.info("Ingestion summary: %s", summary)
        return summary


async def main() -> int:
    """Example entry point for running the ingestion as a script."""
    configure_logging()
    settings = Settings()

    logger.info("Initialized ServiceNow incident ingestion settings.")
    service = ServiceNowIncidentIngestionService(settings)
    summary = await service.ingest()
    print(json.dumps(summary, indent=2, default=str))
    return 1 if summary["total_fetched"] == 0 and summary["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

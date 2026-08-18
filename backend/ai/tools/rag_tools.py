from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import AzureOpenAIEmbeddings
from langchain_chroma import Chroma


logger = logging.getLogger(__name__)


class RAGToolError(Exception):
    """Base RAG exception."""


class RAGConfigurationError(RAGToolError):
    """RAG configuration error."""


class RAGSearchError(RAGToolError):
    """RAG retrieval error."""


class RAGTool:
    """
    Production RAG retrieval service.

    Azure AI Search:
        - Hybrid search
        - Vector search
        - Keyword search
        - Semantic ranking
        - Metadata filtering

    Local ChromaDB:
        - Semantic similarity search only
        - No metadata filtering
        - No hybrid search
        - No reranking
    """

    def __init__(self) -> None:

        self.top_k_default = int(
            os.getenv(
                "RAG_TOP_K",
                "5",
            )
        )

        self.chroma_directory = os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            "./data/chroma",
        )

        self.chroma_collection = os.getenv(
            "CHROMA_COLLECTION_NAME",
            "incidents",
        )

        self._embeddings: AzureOpenAIEmbeddings | None = None
        self._chroma: Chroma | None = None

    # ============================================================
    # Configuration
    # ============================================================

    @staticmethod
    def _azure_search_configured() -> bool:
        required = (
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_API_KEY",
            "AZURE_SEARCH_INDEX_NAME",
        )

        return all(
            os.getenv(key)
            for key in required
        )

    # ============================================================
    # Embeddings
    # ============================================================

    def _get_embeddings(self) -> AzureOpenAIEmbeddings:

        if self._embeddings is not None:
            return self._embeddings

        required = (
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        )

        missing = [
            key
            for key in required
            if not os.getenv(key)
        ]

        if missing:
            raise RAGConfigurationError(
                "Missing Azure OpenAI embedding "
                f"configuration: {', '.join(missing)}"
            )

        self._embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=os.environ[
                "AZURE_OPENAI_ENDPOINT"
            ],
            api_key=os.environ[
                "AZURE_OPENAI_API_KEY"
            ],
            azure_deployment=os.environ[
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
            ],
            api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION",
                "2024-02-01",
            ),
        )

        return self._embeddings

    # ============================================================
    # ChromaDB
    # ============================================================

    def _get_chroma(self) -> Chroma:

        if self._chroma is not None:
            return self._chroma

        try:

            self._chroma = Chroma(
                collection_name=self.chroma_collection,
                persist_directory=self.chroma_directory,
                embedding_function=self._get_embeddings(),
            )

        except Exception as exc:

            logger.exception(
                "Failed to initialize ChromaDB."
            )

            raise RAGConfigurationError(
                "Unable to initialize local ChromaDB."
            ) from exc

        return self._chroma

    def _search_chroma(
        self,
        query: str,
        top_k: int,
    ) -> list[Document]:
        """
        ChromaDB semantic search only.

        Intentionally does NOT use:
            - metadata filtering
            - hybrid search
            - reranking
        """

        try:

            vectorstore = self._get_chroma()

            return vectorstore.similarity_search(
                query=query,
                k=top_k,
            )

        except Exception as exc:

            logger.exception(
                "ChromaDB semantic search failed."
            )

            raise RAGSearchError(
                "ChromaDB semantic search failed."
            ) from exc

    # ============================================================
    # Azure AI Search
    # ============================================================

    def _build_azure_filter(
        self,
        assignment_group: str | None,
        start_datetime: str | None,
        end_datetime: str | None,
    ) -> str | None:
        """
        Build Azure AI Search OData filter.

        Expected Azure Search fields:

            assignment_group
            incident_datetime

        Both fields must be filterable in the
        Azure AI Search index.

        Example:

            assignment_group eq 'Network Support'
            and incident_datetime ge 2026-01-01T00:00:00Z
            and incident_datetime le 2026-08-18T23:59:59Z
        """

        filters: list[str] = []

        if assignment_group:

            escaped_group = (
                assignment_group
                .replace("'", "''")
            )

            filters.append(
                f"assignment_group eq "
                f"'{escaped_group}'"
            )

        if start_datetime:

            filters.append(
                "incident_datetime ge "
                f"{self._format_odata_datetime(start_datetime)}"
            )

        if end_datetime:

            filters.append(
                "incident_datetime le "
                f"{self._format_odata_datetime(end_datetime)}"
            )

        if not filters:
            return None

        return " and ".join(filters)

    @staticmethod
    def _format_odata_datetime(
        value: str,
    ) -> str:
        """
        Validate/normalize a datetime value for
        Azure AI Search OData filtering.

        Expected input examples:

            2026-08-01T00:00:00Z
            2026-08-01T00:00:00+00:00
        """

        value = value.strip()

        if not value:
            raise ValueError(
                "Datetime filter cannot be empty."
            )

        # Azure AI Search OData Edm.DateTimeOffset
        # values should be ISO-8601.
        if not (
            "T" in value
            and (
                value.endswith("Z")
                or "+" in value
                or value.endswith("-00:00")
            )
        ):
            raise ValueError(
                "Datetime must be ISO-8601 format, "
                "for example "
                "'2026-08-01T00:00:00Z'."
            )

        return value

    def _search_azure(
        self,
        query: str,
        top_k: int,
        assignment_group: str | None,
        start_datetime: str | None,
        end_datetime: str | None,
    ) -> list[Document]:

        try:

            from azure.core.credentials import (
                AzureKeyCredential,
            )

            from azure.search.documents import (
                SearchClient,
            )

        except ImportError as exc:

            raise RAGConfigurationError(
                "Azure AI Search dependencies are not "
                "installed."
            ) from exc

        endpoint = os.environ[
            "AZURE_SEARCH_ENDPOINT"
        ]

        api_key = os.environ[
            "AZURE_SEARCH_API_KEY"
        ]

        index_name = os.environ[
            "AZURE_SEARCH_INDEX_NAME"
        ]

        content_field = os.getenv(
            "AZURE_SEARCH_CONTENT_FIELD",
            "content",
        )

        vector_field = os.getenv(
            "AZURE_SEARCH_VECTOR_FIELD",
            "content_vector",
        )

        semantic_configuration = os.getenv(
            "AZURE_SEARCH_SEMANTIC_CONFIGURATION",
            "default",
        )

        filter_expression = (
            self._build_azure_filter(
                assignment_group=assignment_group,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
            )
        )

        try:

            client = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=AzureKeyCredential(
                    api_key
                ),
            )

            # ----------------------------------------------------
            # Create query embedding
            # ----------------------------------------------------

            embedding = (
                self._get_embeddings()
                .embed_query(query)
            )

            # ----------------------------------------------------
            # Azure AI Search Vector Query
            # ----------------------------------------------------

            from azure.search.documents.models import (
                VectorizedQuery,
            )

            vector_query = VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=top_k,
                fields=vector_field,
            )

            # ----------------------------------------------------
            # Hybrid + Semantic Search
            # ----------------------------------------------------

            results = client.search(
                search_text=query,
                vector_queries=[
                    vector_query
                ],
                filter=filter_expression,
                query_type="semantic",
                semantic_configuration_name=(
                    semantic_configuration
                ),
                query_caption="extractive",
                query_answer="extractive",
                top=top_k,
            )

            documents: list[Document] = []

            for result in results:

                content = result.get(
                    content_field,
                    "",
                )

                if not content:
                    continue

                metadata = {
                    key: value
                    for key, value in result.items()
                    if key != content_field
                    and key != vector_field
                    and not key.startswith("@search.")
                }

                # Keep Azure ranking information.
                if result.get("@search.score") is not None:

                    metadata["search_score"] = (
                        result["@search.score"]
                    )

                if result.get(
                    "@search.rerankerScore"
                ) is not None:

                    metadata["reranker_score"] = (
                        result[
                            "@search.rerankerScore"
                        ]
                    )

                documents.append(
                    Document(
                        page_content=str(
                            content
                        ),
                        metadata=metadata,
                    )
                )

            return documents

        except Exception as exc:

            logger.exception(
                "Azure AI Search failed."
            )

            raise RAGSearchError(
                "Azure AI Search hybrid/semantic "
                "search failed."
            ) from exc

    # ============================================================
    # Public Search
    # ============================================================

    def search(
        self,
        query: str,
        top_k: int | None = None,
        assignment_group: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute RAG retrieval.

        Args:
            query:
                Incident/problem search query.

            top_k:
                Number of results.

            assignment_group:
                Optional assignment-group filter.

            start_datetime:
                Optional ISO-8601 start datetime.

            end_datetime:
                Optional ISO-8601 end datetime.

        Azure AI Search:
            Hybrid + semantic ranking + metadata filtering.

        ChromaDB:
            Semantic similarity only.
        """

        query = query.strip()

        if not query:
            raise ValueError(
                "RAG query cannot be empty."
            )

        if top_k is None:
            top_k = self.top_k_default

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        # ========================================================
        # Azure AI Search
        # ========================================================

        if self._azure_search_configured():

            documents = self._search_azure(
                query=query,
                top_k=top_k,
                assignment_group=assignment_group,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
            )

            backend = "azure_ai_search"

            search_mode = (
                "hybrid + semantic reranking"
            )

            filters_applied = {
                "assignment_group":
                    assignment_group,
                "start_datetime":
                    start_datetime,
                "end_datetime":
                    end_datetime,
            }

        # ========================================================
        # Local ChromaDB
        # ========================================================

        else:

            documents = self._search_chroma(
                query=query,
                top_k=top_k,
            )

            backend = "local_chromadb"

            search_mode = "semantic_similarity"

            # Chroma intentionally ignores metadata filters.
            filters_applied = {}

        # ========================================================
        # Normalize response
        # ========================================================

        return {
            "success": True,
            "backend": backend,
            "search_mode": search_mode,
            "query": query,
            "filters_applied": filters_applied,
            "result_count": len(documents),
            "results": [
                self._document_to_result(
                    document
                )
                for document in documents
            ],
        }

    @staticmethod
    def _document_to_result(
        document: Document,
    ) -> dict[str, Any]:

        return {
            "content": document.page_content,
            "metadata": document.metadata,
        }


# ================================================================
# Singleton
# ================================================================

rag_service = RAGTool()


# ================================================================
# LangGraph Tool
# ================================================================

@tool
def rag_search(
    query: str,
    top_k: int = 5,
    assignment_group: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
) -> dict[str, Any]:
    """
    Search historical incidents and incident-resolution
    knowledge.

    Azure AI Search:
        Uses hybrid search combining keyword and vector
        search, followed by Azure semantic ranking.

        Supports optional metadata filtering:
            - assignment_group
            - start_datetime
            - end_datetime

    Local ChromaDB:
        Uses semantic similarity search only.

        Metadata filtering, hybrid search, and reranking
        are intentionally not used for ChromaDB.

    Date/time filters are optional.

    Datetime format:

        2026-08-01T00:00:00Z

    Examples:

        rag_search(
            query="database connection timeout",
            top_k=5
        )

        rag_search(
            query="database connection timeout",
            top_k=5,
            assignment_group="Database Support"
        )

        rag_search(
            query="application unavailable",
            top_k=5,
            assignment_group="Application Support",
            start_datetime="2026-07-01T00:00:00Z",
            end_datetime="2026-08-18T23:59:59Z"
        )
    """

    return rag_service.search(
        query=query,
        top_k=top_k,
        assignment_group=assignment_group,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )
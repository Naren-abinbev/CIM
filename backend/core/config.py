from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    """Read a configuration value and remove accidental surrounding whitespace."""
    return os.getenv(name, default).strip()


def _score_env(name: str, default: str) -> float:
    value = float(_env(name, default))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def _project_path(name: str, default: str) -> str:
    """Resolve relative data paths consistently, regardless of current directory."""
    value = Path(_env(name, default)).expanduser()
    return str(value if value.is_absolute() else PROJECT_ROOT / value)


class Settings:
    """
    Application configuration loaded from environment variables.

    Secrets are never logged or exposed in error messages.
    """

    # Application
    app_name: str = os.getenv("APP_NAME", "ai-incident-management")
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    server_host: str = os.getenv("HOST", "0.0.0.0")
    server_port: int = int(os.getenv("PORT", "8000"))

    # JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    jwt_issuer: str | None = os.getenv("JWT_ISSUER") or None
    jwt_audience: str | None = os.getenv("JWT_AUDIENCE") or None

    # CORS
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8501")

    # Cookies
    secure_cookies: bool = os.getenv("SECURE_COOKIES", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    streamlit_cookie_secret: str = os.getenv("STREAMLIT_COOKIE_SECRET", "")

    # Database
    sqlite_database_path: str = _project_path(
        "SQLITE_DATABASE_PATH",
        "data/sqlite/cim.db",
    )

    # Agent identifiers
    # Agent IDs are deployment configuration, not application code.
    agent_id_sample_investigation_agent: str = _env(
        "AGENT_ID_SAMPLE_INVESTIGATION_AGENT"
    )

    # Gemini embeddings
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_embedding_model: str = os.getenv(
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )

    # Azure AI Search
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    azure_search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY", "")
    azure_search_index_name: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "incidents")

    # ChromaDB fallback
    chroma_persist_directory: str = _project_path(
        "CHROMA_PERSIST_DIRECTORY",
        "./data/chroma",
    )
    chroma_collection_name: str = os.getenv(
        "CHROMA_COLLECTION_NAME",
        "incidents",
    )
    search_min_relevance_score: float = _score_env(
        "SEARCH_MIN_RELEVANCE_SCORE",
        "0.75",
    )

    # ServiceNow ingestion
    servicenow_instance_url: str = _env("SERVICENOW_INSTANCE_URL")
    servicenow_username: str = _env("SERVICENOW_USERNAME")
    servicenow_password: str = _env("SERVICENOW_PASSWORD")
    servicenow_client_id: str = _env("SERVICENOW_CLIENT_ID")
    servicenow_client_secret: str = _env("SERVICENOW_CLIENT_SECRET")
    servicenow_page_size: int = int(os.getenv("SERVICENOW_PAGE_SIZE", "100"))
    ingestion_concurrency: int = int(os.getenv("INGESTION_CONCURRENCY", "5"))
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "30"))

    @property
    def azure_search_available(self) -> bool:
        values = (
            self.azure_search_endpoint,
            self.azure_search_api_key,
            self.azure_search_index_name,
        )
        return all(
            value.strip() and not value.strip().startswith("<")
            for value in values
        )

    # Password policy
    min_password_length: int = int(
        os.getenv("MIN_PASSWORD_LENGTH", "12")
    )
    bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Rate limiting
    rate_limit_enabled: bool = os.getenv(
        "RATE_LIMIT_ENABLED",
        "true",
    ).lower() in {"1", "true", "yes", "on"}

    rate_limit_max_requests: int = int(
        os.getenv("RATE_LIMIT_MAX_REQUESTS", "10")
    )

    rate_limit_window_seconds: int = int(
        os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    )

    @property
    def jwt_secret_configured(self) -> bool:
        return bool(self.jwt_secret_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

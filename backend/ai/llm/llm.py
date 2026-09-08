from __future__ import annotations

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI


load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# AZURE OPENAI
# ============================================================


class AzureLLMConfigurationError(Exception):
    """Raised when Azure OpenAI LLM configuration is invalid."""


def _get_required_env(name: str) -> str:
    """
    Get a required environment variable.

    Secrets are never included in error messages.
    """

    value = os.getenv(name)

    if not value or not value.strip():
        raise AzureLLMConfigurationError(
            f"Required environment variable '{name}' "
            "is not configured."
        )

    return value.strip()


@lru_cache(maxsize=1)
def get_azure_llm() -> AzureChatOpenAI:
    """
    Create and cache the shared Azure OpenAI LLM client.

    All LangGraph agents should use this factory instead
    of creating their own AzureChatOpenAI instance.

    Required environment variables:

        AZURE_OPENAI_ENDPOINT
        AZURE_OPENAI_API_KEY
        AZURE_OPENAI_DEPLOYMENT

    Optional:

        AZURE_OPENAI_API_VERSION
        AZURE_OPENAI_TEMPERATURE
        AZURE_OPENAI_MAX_TOKENS
        AZURE_OPENAI_TIMEOUT
        AZURE_OPENAI_MAX_RETRIES
    """

    endpoint = _get_required_env(
        "AZURE_OPENAI_ENDPOINT"
    )

    api_key = _get_required_env(
        "AZURE_OPENAI_API_KEY"
    )

    deployment = _get_required_env(
        "AZURE_OPENAI_DEPLOYMENT"
    )

    api_version = os.getenv(
        "AZURE_OPENAI_API_VERSION",
        "2024-10-21",
    )

    temperature = float(
        os.getenv(
            "AZURE_OPENAI_TEMPERATURE",
            "0",
        )
    )

    max_tokens_raw = os.getenv(
        "AZURE_OPENAI_MAX_TOKENS"
    )

    max_tokens = (
        int(max_tokens_raw)
        if max_tokens_raw
        else None
    )

    timeout = float(
        os.getenv(
            "AZURE_OPENAI_TIMEOUT",
            "60",
        )
    )

    max_retries = int(
        os.getenv(
            "AZURE_OPENAI_MAX_RETRIES",
            "3",
        )
    )

    try:

        llm = AzureChatOpenAI(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_key=api_key,
            api_version=api_version,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )

    except Exception as exc:

        logger.exception(
            "Failed to initialize Azure OpenAI LLM."
        )

        raise AzureLLMConfigurationError(
            "Unable to initialize Azure OpenAI LLM."
        ) from exc

    logger.info(
        "Azure OpenAI LLM initialized successfully "
        "using deployment '%s'.",
        deployment,
    )

    return llm


# ============================================================
# GEMINI
# ============================================================


class GeminiLLMConfigurationError(Exception):
    """Raised when Gemini LLM configuration is invalid."""


def _get_required_gemini_env(name: str) -> str:
    """
    Get a required Gemini environment variable.

    Secrets are never included in error messages.
    """

    value = os.getenv(name)

    if not value or not value.strip():
        raise GeminiLLMConfigurationError(
            f"Required environment variable '{name}' "
            "is not configured."
        )

    return value.strip()


class GeminiLLM:
    """Create a configured LangChain Gemini client."""

    def __init__(self) -> None:
        self.api_key = _get_required_gemini_env(
            "GEMINI_API_KEY"
        )

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.7-flash",
        ).strip()

        self.temperature = float(
            os.getenv(
                "GEMINI_TEMPERATURE",
                "0",
            )
        )

        max_tokens_raw = os.getenv(
            "GEMINI_MAX_TOKENS"
        )

        self.max_tokens = (
            int(max_tokens_raw)
            if max_tokens_raw
            else None
        )

        self.timeout = float(
            os.getenv(
                "GEMINI_TIMEOUT",
                "60",
            )
        )

        self.max_retries = int(
            os.getenv(
                "GEMINI_MAX_RETRIES",
                "3",
            )
        )

    def create_client(self) -> ChatGoogleGenerativeAI:
        """Create the Gemini client."""

        try:
            return ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

        except Exception as exc:
            logger.exception(
                "Failed to initialize Gemini LLM."
            )

            raise GeminiLLMConfigurationError(
                "Unable to initialize Gemini LLM."
            ) from exc


@lru_cache(maxsize=1)
def get_gemini_llm() -> ChatGoogleGenerativeAI:
    """
    Create and cache the shared Gemini client.
    """

    configuration = GeminiLLM()
    llm = configuration.create_client()

    logger.info(
        "Gemini initialized successfully using model '%s'.",
        configuration.model,
    )

    return llm
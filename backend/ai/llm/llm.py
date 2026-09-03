from __future__ import annotations

import logging
import os
from functools import lru_cache

from langchain_openai import AzureChatOpenAI


logger = logging.getLogger(__name__)


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
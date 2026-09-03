from __future__ import annotations

import asyncio
import os

import pytest

from backend.core.config import get_settings
from backend.rag.servicenow_incident_ingestion import (
    GeminiEmbeddingClient,
    GeminiEmbeddingError,
)


# Approximate input sizes in characters. The script stops at the first failure.
DEFAULT_TEST_SIZES = (1_000, 8_000, 16_000, 32_000, 64_000)


def _test_text(character_count: int) -> str:
    sentence = (
        "This is a synthetic incident description used to test Gemini embedding "
        "input limits without sending credentials or production incident data. "
    )
    repetitions = (character_count // len(sentence)) + 1
    return (sentence * repetitions)[:character_count]


async def run_token_limit_test() -> None:
    settings = get_settings()
    if not settings.gemini_api_key.strip():
        raise RuntimeError("GEMINI_API_KEY is not configured in .env")

    sizes = tuple(
        int(value.strip())
        for value in os.getenv(
            "GEMINI_TOKEN_TEST_SIZES",
            ",".join(str(size) for size in DEFAULT_TEST_SIZES),
        ).split(",")
        if value.strip()
    )
    client = GeminiEmbeddingClient(settings)

    print(f"model={settings.gemini_embedding_model}")
    print(f"test_sizes_chars={sizes}")

    for character_count in sizes:
        try:
            embedding = await client.generate_embedding(_test_text(character_count))
        except GeminiEmbeddingError as exc:
            cause = exc.__cause__
            print(f"FAIL chars={character_count} error={type(cause or exc).__name__}")
            print(f"details={str(cause or exc)[:500]}")
            print("The request exceeded a provider limit or was rejected by the API.")
            return

        print(f"PASS chars={character_count} embedding_dimensions={len(embedding)}")

    print("All tested input sizes were accepted; no limit was reached.")


def test_gemini_token_limit() -> None:
    """Opt-in pytest wrapper for the live Gemini limit test."""
    if os.getenv("RUN_GEMINI_LIVE_TEST") != "1":
        pytest.skip("Set RUN_GEMINI_LIVE_TEST=1 to run the live Gemini API test")
    asyncio.run(run_token_limit_test())


if __name__ == "__main__":
    asyncio.run(run_token_limit_test())

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import requests
from azure.identity import ClientSecretCredential


logger = logging.getLogger(__name__)


class MicrosoftGraphError(Exception):
    """Base exception for Microsoft Graph errors."""


class MicrosoftGraphAuthenticationError(
    MicrosoftGraphError
):
    """Authentication failure."""


class MicrosoftGraphAPIError(
    MicrosoftGraphError
):
    """Microsoft Graph API failure."""


class MicrosoftGraphClient:
    """
    Production Microsoft Graph client.

    Responsibilities:
    - Acquire Entra ID access token
    - Cache token until shortly before expiry
    - Automatically refresh expired tokens
    - Execute Graph API requests
    - Handle transient HTTP failures
    - Never expose credentials/tokens to agents
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    GRAPH_SCOPE = "https://graph.microsoft.com/.default"

    def __init__(self) -> None:

        self.tenant_id = self._required_env(
            "GRAPH_TENANT_ID"
        )

        self.client_id = self._required_env(
            "GRAPH_CLIENT_ID"
        )

        self.client_secret = self._required_env(
            "GRAPH_CLIENT_SECRET"
        )

        self.timeout = int(
            os.getenv(
                "GRAPH_API_TIMEOUT_SECONDS",
                "30",
            )
        )

        self.max_retries = int(
            os.getenv(
                "GRAPH_API_MAX_RETRIES",
                "3",
            )
        )

        self._credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        self._token: str | None = None
        self._token_expires_at: float = 0

        self._token_lock = threading.Lock()

        self._session = requests.Session()

    @staticmethod
    def _required_env(name: str) -> str:

        value = os.getenv(name)

        if not value:
            raise RuntimeError(
                f"Required environment variable "
                f"'{name}' is not configured."
            )

        return value

    def _get_access_token(self) -> str:
        """
        Get cached token or acquire a new one.

        Token is refreshed 5 minutes before expiry.
        """

        current_time = time.time()

        if (
            self._token
            and current_time
            < self._token_expires_at - 300
        ):
            return self._token

        with self._token_lock:

            current_time = time.time()

            if (
                self._token
                and current_time
                < self._token_expires_at - 300
            ):
                return self._token

            try:

                token = self._credential.get_token(
                    self.GRAPH_SCOPE
                )

            except Exception as exc:

                logger.exception(
                    "Microsoft Graph authentication failed."
                )

                raise MicrosoftGraphAuthenticationError(
                    "Unable to authenticate with "
                    "Microsoft Graph."
                ) from exc

            self._token = token.token
            self._token_expires_at = token.expires_on

            return self._token

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        url = (
            endpoint
            if endpoint.startswith("http")
            else f"{self.GRAPH_BASE_URL}{endpoint}"
        )

        last_exception: Exception | None = None

        for attempt in range(
            self.max_retries + 1
        ):

            try:

                token = self._get_access_token()

                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }

                response = self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )

                # Token may have been revoked/expired.
                # Refresh once and retry.
                if response.status_code == 401:

                    self._invalidate_token()

                    if attempt < self.max_retries:
                        continue

                # Retry transient errors.
                if response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    if attempt < self.max_retries:

                        self._sleep_before_retry(
                            attempt,
                            response,
                        )

                        continue

                if not response.ok:

                    self._raise_api_error(
                        response
                    )

                if not response.content:
                    return {}

                return response.json()

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_exception = exc

                if attempt < self.max_retries:

                    self._sleep_before_retry(
                        attempt
                    )

                    continue

                raise MicrosoftGraphAPIError(
                    "Microsoft Graph request failed "
                    "after retries."
                ) from exc

        raise MicrosoftGraphAPIError(
            "Microsoft Graph request failed."
        ) from last_exception

    def _invalidate_token(self) -> None:

        with self._token_lock:

            self._token = None
            self._token_expires_at = 0

    def _sleep_before_retry(
        self,
        attempt: int,
        response: requests.Response | None = None,
    ) -> None:

        retry_after = None

        if response is not None:

            retry_after = response.headers.get(
                "Retry-After"
            )

        if retry_after:

            try:
                delay = float(retry_after)

            except ValueError:
                delay = 2 ** attempt

        else:
            delay = 2 ** attempt

        delay = min(delay, 30)

        time.sleep(delay)

    @staticmethod
    def _raise_api_error(
        response: requests.Response,
    ) -> None:

        try:
            error_body = response.json()

        except ValueError:
            error_body = response.text

        logger.error(
            "Microsoft Graph API error: "
            "status=%s body=%s",
            response.status_code,
            error_body,
        )

        raise MicrosoftGraphAPIError(
            f"Microsoft Graph API returned "
            f"HTTP {response.status_code}."
        )

    def close(self) -> None:

        self._session.close()
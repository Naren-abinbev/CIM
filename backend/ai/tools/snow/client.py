from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import requests


logger = logging.getLogger(__name__)


class ServiceNowError(Exception):
    """Base ServiceNow exception."""


class ServiceNowAuthenticationError(
    ServiceNowError
):
    """ServiceNow authentication failure."""


class ServiceNowAPIError(
    ServiceNowError
):
    """ServiceNow API failure."""


class ServiceNowClient:
    """
    Production ServiceNow REST client.

    Uses OAuth client credentials.

    Responsibilities:
    - Generate OAuth access token
    - Cache token
    - Refresh token before expiry
    - Retry transient failures
    - Execute ServiceNow REST requests
    """

    def __init__(self) -> None:

        self.instance_url = self._required_env(
            "SERVICENOW_INSTANCE_URL"
        ).rstrip("/")

        self.client_id = self._required_env(
            "SERVICENOW_CLIENT_ID"
        )

        self.client_secret = self._required_env(
            "SERVICENOW_CLIENT_SECRET"
        )

        self.timeout = int(
            os.getenv(
                "SERVICENOW_API_TIMEOUT_SECONDS",
                "30",
            )
        )

        self.max_retries = int(
            os.getenv(
                "SERVICENOW_API_MAX_RETRIES",
                "3",
            )
        )

        self.oauth_url = (
            f"{self.instance_url}"
            "/oauth_token.do"
        )

        self.api_base_url = (
            f"{self.instance_url}"
            "/api/now/table"
        )

        self._access_token: str | None = None
        self._expires_at: float = 0

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
        Return cached OAuth token or generate
        a new one.
        """

        now = time.time()

        if (
            self._access_token
            and now < self._expires_at - 300
        ):
            return self._access_token

        with self._token_lock:

            now = time.time()

            if (
                self._access_token
                and now < self._expires_at - 300
            ):
                return self._access_token

            try:

                response = self._session.post(
                    self.oauth_url,
                    data={
                        "grant_type":
                            "client_credentials",
                        "client_id":
                            self.client_id,
                        "client_secret":
                            self.client_secret,
                    },
                    headers={
                        "Accept":
                            "application/json",
                    },
                    timeout=self.timeout,
                )

            except requests.RequestException as exc:

                logger.exception(
                    "ServiceNow OAuth request failed."
                )

                raise ServiceNowAuthenticationError(
                    "Unable to connect to "
                    "ServiceNow OAuth endpoint."
                ) from exc

            if not response.ok:

                logger.error(
                    "ServiceNow OAuth failed: "
                    "HTTP %s",
                    response.status_code,
                )

                raise ServiceNowAuthenticationError(
                    "ServiceNow OAuth authentication "
                    "failed."
                )

            data = response.json()

            access_token = data.get(
                "access_token"
            )

            if not access_token:
                raise ServiceNowAuthenticationError(
                    "ServiceNow OAuth response did "
                    "not contain an access token."
                )

            expires_in = int(
                data.get(
                    "expires_in",
                    1800,
                )
            )

            self._access_token = access_token

            self._expires_at = (
                time.time()
                + expires_in
            )

            return self._access_token

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
            else f"{self.api_base_url}{endpoint}"
        )

        for attempt in range(
            self.max_retries + 1
        ):

            try:

                token = (
                    self._get_access_token()
                )

                headers = {
                    "Authorization":
                        f"Bearer {token}",
                    "Accept":
                        "application/json",
                    "Content-Type":
                        "application/json",
                }

                response = (
                    self._session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json,
                        timeout=self.timeout,
                    )
                )

                if response.status_code == 401:

                    self._invalidate_token()

                    if attempt < self.max_retries:
                        continue

                if response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    if attempt < self.max_retries:

                        self._sleep_before_retry(
                            attempt
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

                if attempt < self.max_retries:

                    self._sleep_before_retry(
                        attempt
                    )

                    continue

                raise ServiceNowAPIError(
                    "ServiceNow request failed "
                    "after retries."
                ) from exc

        raise ServiceNowAPIError(
            "ServiceNow request failed."
        )

    def _invalidate_token(self) -> None:

        with self._token_lock:

            self._access_token = None
            self._expires_at = 0

    @staticmethod
    def _sleep_before_retry(
        attempt: int,
    ) -> None:

        delay = min(
            2 ** attempt,
            30,
        )

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
            "ServiceNow API error: "
            "status=%s body=%s",
            response.status_code,
            error_body,
        )

        raise ServiceNowAPIError(
            f"ServiceNow API returned "
            f"HTTP {response.status_code}."
        )

    def close(self) -> None:

        self._session.close()
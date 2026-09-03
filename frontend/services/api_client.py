"""Small, auth-only HTTP client used by the Streamlit entry point."""

from __future__ import annotations

import os
from typing import Any

import requests


class AuthenticationApiError(Exception):
    """Safe message returned by the authentication API."""


class AuthApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_API_URL", "http://localhost:8000")).rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.request(method, f"{self.base_url}{path}", timeout=10, **kwargs)
        except requests.RequestException as exc:
            raise AuthenticationApiError("Authentication service is unavailable.") from exc
        if response.ok:
            return response.json()
        try:
            message = response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = "Authentication request failed."
        raise AuthenticationApiError(message)

    def register(self, *, username: str, email: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/auth/register", json={"username": username, "email": email, "password": password})

    def login(self, *, username: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/auth/login", json={"username": username, "password": password})

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._request("POST", "/auth/refresh", json={"refresh_token": refresh_token})

    def logout(self, refresh_token: str) -> None:
        self._request("POST", "/auth/logout", json={"refresh_token": refresh_token})

    def me(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", "/auth/me", headers={"Authorization": f"Bearer {access_token}"})

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("cim.audit")


class AuditLogger:
    """
    Structured security audit logger.

    Records security-relevant events without exposing secrets.

    Never logs:
    - passwords
    - access tokens
    - refresh tokens
    - JWT secrets
    - password hashes
    """

    @staticmethod
    def _emit(
        *,
        event: str,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "event": event,
            "timestamp": time.time(),
        }

        if user_id:
            record["user_id"] = user_id

        if request_id:
            record["request_id"] = request_id

        if ip_address:
            record["ip_address"] = ip_address

        if extra:
            record.update(extra)

        logger.info(json.dumps(record, default=str))

    @classmethod
    def login_success(
        cls,
        *,
        user_id: str,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="LOGIN_SUCCESS",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def login_failure(
        cls,
        *,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="LOGIN_FAILURE",
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def token_refresh(
        cls,
        *,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="TOKEN_REFRESH",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def token_refresh_reuse_detected(
        cls,
        *,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="TOKEN_REFRESH_REUSE_DETECTED",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def logout(
        cls,
        *,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="LOGOUT",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def account_disabled(
        cls,
        *,
        user_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="ACCOUNT_DISABLED",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

    @classmethod
    def registration(
        cls,
        *,
        user_id: str,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        cls._emit(
            event="REGISTRATION",
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
        )

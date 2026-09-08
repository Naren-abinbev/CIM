from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("cim.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured request logging.

    Never logs authorization headers, tokens, or passwords.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        request_id = getattr(
            request.state,
            "request_id",
            None,
        )

        response = await call_next(request)

        duration_ms = (time.monotonic() - start) * 1000

        logger.info(
            "method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )

        return response
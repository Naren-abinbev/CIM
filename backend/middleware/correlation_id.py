from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Attach a correlation/request ID to every request.

    Uses an incoming X-Request-ID if present, otherwise
    generates a new UUID. The ID is stored on the request
    state and echoed back in the response header.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response
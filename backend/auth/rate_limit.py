from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding-window in-memory rate limiter.

    This is a local development fallback. Production deployments
    must enforce the same limits at the API gateway or use a shared
    rate-limit backend; a per-process counter cannot protect a
    multi-instance service.
    """

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        window_start = now - self.window_seconds
        hits = self._hits[key]

        while hits and hits[0] < window_start:
            hits.popleft()

    def check(self, key: str) -> bool:
        """
        Record a hit for `key` and return whether it is allowed.
        """
        now = time.monotonic()

        with self._lock:
            self._prune(key, now)

            hits = self._hits[key]

            if len(hits) >= self.max_requests:
                return False

            hits.append(now)
            return True


def _client_key(request: Request) -> str:
    """
    Build a rate-limit key from the client IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    return client_ip


def rate_limit(
    *,
    max_requests: int | None = None,
    window_seconds: int | None = None,
) -> Callable[[Request], None]:
    """
    FastAPI dependency that rate-limits a route per client IP.

    When RATE_LIMIT_ENABLED=false, the dependency is a no-op.
    """
    settings = get_settings()

    limiter = RateLimiter(
        max_requests=max_requests
        or settings.rate_limit_max_requests,
        window_seconds=window_seconds
        or settings.rate_limit_window_seconds,
    )

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return

        key = _client_key(request)

        if not limiter.check(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again later.",
                    }
                },
            )

    return dependency

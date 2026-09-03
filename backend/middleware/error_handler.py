from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    """Return the correlation ID from request state, or generate one."""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    """Return a consistent error schema."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
    )


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    - Catches unhandled exceptions and returns a consistent
      error schema without exposing internal details.
    - Normalises Starlette HTTPException and Pydantic
      validation errors into the same schema.
    - Never logs request bodies, authorization headers,
      passwords, or tokens.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = _request_id(request)

        try:
            response = await call_next(request)
        except RequestValidationError as exc:
            logger.warning(
                "validation_error request_id=%s errors=%s",
                request_id,
                jsonable_encoder(exc.errors()),
            )
            return _error_response(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                request_id=request_id,
            )
        except StarletteHTTPException as exc:
            # Already a structured error detail dict — pass through.
            if isinstance(exc.detail, dict) and "error" in exc.detail:
                detail = exc.detail["error"]
                return _error_response(
                    status_code=exc.status_code,
                    code=detail.get("code", "HTTP_ERROR"),
                    message=detail.get("message", "Request failed."),
                    request_id=detail.get("request_id", request_id),
                )
            return _error_response(
                status_code=exc.status_code,
                code="HTTP_ERROR",
                message=str(exc.detail),
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001 - global safety net
            logger.exception(
                "unhandled_error request_id=%s",
                request_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return _error_response(
                status_code=500,
                code="INTERNAL_ERROR",
                message="An internal error occurred.",
                request_id=request_id,
            )

        return response
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.auth import service
from backend.auth.rate_limit import rate_limit
from backend.database.database import get_db
from backend.database.models import User
from backend.logging.audit_logger import AuditLogger
from backend.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


def _request_context(request: Request) -> tuple[str | None, str | None]:
    request_id = getattr(request.state, "request_id", None)
    ip_address = request.client.host if request.client else None
    return request_id, ip_address


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit())],
)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> RegisterResponse:
    request_id, ip_address = _request_context(request)

    try:
        user = service.register_user(
            db,
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "REGISTRATION_FAILED",
                    "message": str(exc),
                }
            },
        ) from exc

    AuditLogger.registration(
        user_id=user.id,
        request_id=request_id,
        ip_address=ip_address,
    )

    return RegisterResponse(
        id=user.id,
        username=user.username,
        email=user.email,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit())],
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> TokenResponse:
    request_id, ip_address = _request_context(request)

    try:
        user = service.authenticate_user(
            db,
            username=payload.username,
            password=payload.password,
        )
    except service.InvalidCredentialsError:
        AuditLogger.login_failure(
            request_id=request_id,
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Invalid username or password.",
                }
            },
        ) from None
    except service.UserInactiveError:
        AuditLogger.account_disabled(
            request_id=request_id,
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Invalid username or password.",
                }
            },
        ) from None

    tokens = service.issue_token_pair(
        db,
        user=user,
        user_agent=request.headers.get("User-Agent"),
        ip_address=ip_address,
    )

    AuditLogger.login_success(
        user_id=user.id,
        request_id=request_id,
        ip_address=ip_address,
    )

    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit())],
)
def refresh(
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> TokenResponse:
    request_id, ip_address = _request_context(request)

    try:
        tokens = service.refresh_token_pair(
            db,
            raw_refresh_token=payload.refresh_token,
            user_agent=request.headers.get("User-Agent"),
            ip_address=ip_address,
        )
    except service.RefreshTokenReuseError as exc:
        AuditLogger.token_refresh_reuse_detected(
            request_id=request_id,
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "REFRESH_TOKEN_REUSE",
                    "message": str(exc),
                }
            },
        ) from exc
    except service.InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": str(exc),
                }
            },
        ) from exc
    except service.UserInactiveError as exc:
        AuditLogger.account_disabled(
            request_id=request_id,
            ip_address=ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ACCOUNT_DISABLED",
                    "message": str(exc),
                }
            },
        ) from exc

    AuditLogger.token_refresh(
        request_id=request_id,
        ip_address=ip_address,
    )

    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
)
def logout(
    payload: LogoutRequest,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> MessageResponse:
    request_id, ip_address = _request_context(request)

    service.revoke_refresh_token(
        db,
        raw_refresh_token=payload.refresh_token,
    )

    AuditLogger.logout(
        request_id=request_id,
        ip_address=ip_address,
    )

    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )

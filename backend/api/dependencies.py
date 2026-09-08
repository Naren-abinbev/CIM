from __future__ import annotations

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth import security
from backend.database.database import get_db
from backend.database.models import User
from backend.database.repositories import UserRepository
from backend.logging.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access token (JWT)",
)


def _unauthorized(detail: str = "Not authenticated.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": detail,
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> User:
    """
    FastAPI dependency that authenticates the current user.

    Validates the access token and loads the user from SQLite.
    The user identity always comes from the validated token,
    never from the frontend.
    """
    if credentials is None:
        raise _unauthorized()

    token = credentials.credentials

    try:
        payload = security.decode_token(
            token,
            expected_type="access",
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Access token has expired.") from None
    except jwt.PyJWTError:
        raise _unauthorized("Invalid access token.") from None

    user_id = payload.get("sub")

    if not user_id:
        raise _unauthorized("Invalid access token.")

    user = UserRepository.get_by_id(db, user_id)

    if user is None:
        raise _unauthorized("User no longer exists.")

    if not user.is_active:
        AuditLogger.account_disabled(
            user_id=user.id,
            request_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
        raise _unauthorized("Account is disabled.")

    return user


def require_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Alias dependency for readability.
    """
    return user


def require_role(role: str):
    """
    Factory that returns a dependency requiring a specific role.
    """

    def dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Insufficient permissions.",
                    }
                },
            )
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.auth import security
from backend.database.models import User
from backend.database.repositories import (
    RefreshTokenRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Base authentication error."""


class InvalidCredentialsError(AuthenticationError):
    """Username or password is incorrect."""


class UserInactiveError(AuthenticationError):
    """User account is disabled."""


class InvalidRefreshTokenError(AuthenticationError):
    """Refresh token is invalid, expired, or revoked."""


class RefreshTokenReuseError(AuthenticationError):
    """A previously revoked refresh token was reused."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    """Compare SQLite's potentially naive datetimes safely in UTC."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utcnow()


def register_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User:
    """
    Create a new user account.

    Raises ValueError on duplicate username/email.
    """
    if UserRepository.get_by_username(db, username) is not None:
        raise ValueError("Username is already taken.")

    if UserRepository.get_by_email(db, email) is not None:
        raise ValueError("Email is already registered.")

    password_hash = security.hash_password(password)

    return UserRepository.create(
        db,
        username=username,
        email=email,
        password_hash=password_hash,
    )


def authenticate_user(
    db: Session,
    *,
    username: str,
    password: str,
) -> User:
    """
    Validate credentials and return the user.

    Raises InvalidCredentialsError for any failure so that
    username/password enumeration is not possible.
    """
    user = UserRepository.get_by_username(db, username)

    if user is None:
        raise InvalidCredentialsError("Invalid username or password.")

    if not security.verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid username or password.")

    if not user.is_active:
        raise UserInactiveError("Account is disabled.")

    UserRepository.update_last_login(db, user)

    return user


def issue_token_pair(
    db: Session,
    *,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """
    Issue a new access token and refresh token for a user.

    Creates a new refresh-token session record.
    """
    token_family = security.new_token_family()

    access_token, expires_in = security.create_access_token(
        user_id=user.id,
    )

    raw_refresh, refresh_hash, expires_at = (
        security.create_refresh_token(
            user_id=user.id,
            token_family=token_family,
        )
    )

    RefreshTokenRepository.create(
        db,
        user_id=user.id,
        token_hash=refresh_hash,
        token_family=token_family,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_token": raw_refresh,
    }


def refresh_token_pair(
    db: Session,
    *,
    raw_refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """
    Rotate a refresh token and issue a new token pair.

    Steps:
    1. Decode and validate the refresh JWT.
    2. Look up the server-side session record by hash.
    3. Reject if the record is missing, expired, or revoked.
    4. Detect reuse: if the record is already revoked, revoke
       the entire token family and reject.
    5. Revoke the old record.
    6. Issue a new token pair in the same family.
    """
    try:
        payload = security.decode_token(
            raw_refresh_token,
            expected_type="refresh",
        )
    except Exception:
        raise InvalidRefreshTokenError(
            "Invalid refresh token."
        ) from None

    user_id = payload.get("sub")
    token_family = payload.get("family")

    if not user_id or not token_family:
        raise InvalidRefreshTokenError(
            "Invalid refresh token."
        )

    token_hash = security.hash_refresh_token(raw_refresh_token)

    record = RefreshTokenRepository.get_by_hash(db, token_hash)

    if record is None:
        raise InvalidRefreshTokenError(
            "Invalid refresh token."
        )

    # Reuse detection: a revoked token being presented again
    # indicates possible theft/replay. Revoke the whole family.
    if record.revoked_at is not None:
        RefreshTokenRepository.revoke_family(
            db,
            record.token_family,
        )
        raise RefreshTokenReuseError(
            "Refresh token reuse detected. "
            "Please sign in again."
        )

    if _is_expired(record.expires_at):
        raise InvalidRefreshTokenError(
            "Refresh token has expired."
        )

    user = UserRepository.get_by_id(db, record.user_id)

    if user is None or not user.is_active:
        raise UserInactiveError("Account is disabled.")

    # Revoke the old token, linking to its replacement.
    new_refresh, new_refresh_hash, new_expires = (
        security.create_refresh_token(
            user_id=user.id,
            token_family=record.token_family,
        )
    )

    new_record = RefreshTokenRepository.create(
        db,
        user_id=user.id,
        token_hash=new_refresh_hash,
        token_family=record.token_family,
        expires_at=new_expires,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    RefreshTokenRepository.revoke(
        db,
        record,
        replaced_by_token_id=new_record.id,
    )
    RefreshTokenRepository.touch_last_used(db, record)

    access_token, expires_in = security.create_access_token(
        user_id=user.id,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "refresh_token": new_refresh,
    }


def revoke_refresh_token(
    db: Session,
    *,
    raw_refresh_token: str,
) -> None:
    """
    Revoke a refresh-token session (logout).

    The raw token is hashed and matched against the
    server-side record. If found, it is revoked.
    """
    token_hash = security.hash_refresh_token(raw_refresh_token)

    record = RefreshTokenRepository.get_by_hash(db, token_hash)

    if record is not None and record.revoked_at is None:
        RefreshTokenRepository.revoke(db, record)

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================
# Password hashing (bcrypt)
# ============================================================


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    The password is never logged or stored in plaintext.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    Uses bcrypt's constant-time comparison internally.
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        # Malformed hash — treat as invalid, never crash.
        return False


# ============================================================
# JWT helpers
# ============================================================


def _get_secret_key() -> str:
    settings = get_settings()

    if not settings.jwt_secret_configured:
        raise RuntimeError(
            "JWT_SECRET_KEY is not configured. "
            "Set it in the environment before starting the server."
        )

    return settings.jwt_secret_key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    user_id: str,
) -> tuple[str, int]:
    """
    Create a short-lived JWT access token.

    Returns (token, expires_in_seconds).
    """
    settings = get_settings()

    now = _now()

    expires_delta = timedelta(
        minutes=settings.access_token_expire_minutes
    )

    expires_at = now + expires_delta

    payload: dict = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer

    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience

    token = jwt.encode(
        payload,
        _get_secret_key(),
        algorithm=settings.jwt_algorithm,
    )

    return token, int(expires_delta.total_seconds())


def create_refresh_token(
    *,
    user_id: str,
    token_family: str,
) -> tuple[str, str, datetime]:
    """
    Create a long-lived JWT refresh token.

    Returns (raw_token, token_hash, expires_at).

    The raw token is returned to the client only.
    Only the hash is persisted server-side.
    """
    settings = get_settings()

    now = _now()

    expires_delta = timedelta(
        days=settings.refresh_token_expire_days
    )

    expires_at = now + expires_delta

    payload: dict = {
        "sub": user_id,
        "type": "refresh",
        "family": token_family,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer

    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience

    raw_token = jwt.encode(
        payload,
        _get_secret_key(),
        algorithm=settings.jwt_algorithm,
    )

    token_hash = hash_refresh_token(raw_token)

    return raw_token, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    """
    Cryptographically hash a raw refresh token.

    SHA-256 is appropriate here because the token is
    a high-entropy random JWT, not a low-entropy password.
    """
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


def decode_token(token: str, *, expected_type: str) -> dict:
    """
    Decode and validate a JWT.

    Validates:
    - signature
    - expiration
    - token type
    - issuer/audience if configured

    Raises jwt.PyJWTError subclasses on failure.
    """
    settings = get_settings()

    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_iat": True,
        "verify_aud": settings.jwt_audience is not None,
        "require": ["sub", "type", "iat", "exp", "jti"],
    }

    payload = jwt.decode(
        token,
        _get_secret_key(),
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options=options,
    )

    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected token type '{expected_type}'."
        )

    return payload


def new_token_family() -> str:
    return str(uuid.uuid4())


def constant_time_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

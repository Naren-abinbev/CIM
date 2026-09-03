from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-and-not-production")
os.environ.setdefault("BCRYPT_ROUNDS", "4")

from backend.auth import security, service
from backend.core.config import get_settings
from backend.database.database import Base
from backend.database.models import RefreshToken
from backend.database.repositories import RefreshTokenRepository, UserRepository


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _register(db: Session, username: str = "valid_user"):
    return service.register_user(db, username=username, email=f"{username}@example.test", password="A secure password!")


def test_registration_hashes_password_and_enforces_unique_fields(db: Session) -> None:
    user = _register(db)
    assert user.password_hash != "A secure password!"
    assert security.verify_password("A secure password!", user.password_hash)
    with pytest.raises(ValueError, match="Username"):
        _register(db)
    with pytest.raises(ValueError, match="Email"):
        service.register_user(db, username="other_user", email="valid_user@example.test", password="A secure password!")


def test_login_rejects_bad_credentials_and_inactive_user(db: Session) -> None:
    user = _register(db)
    for username, password in (("valid_user", "wrong"), ("missing_user", "wrong")):
        with pytest.raises(service.InvalidCredentialsError, match="Invalid username or password"):
            service.authenticate_user(db, username=username, password=password)
    UserRepository.set_active(db, user, False)
    with pytest.raises(service.UserInactiveError):
        service.authenticate_user(db, username="valid_user", password="A secure password!")


def test_access_token_signature_expiry_claims_and_type_are_validated(db: Session) -> None:
    user = _register(db)
    access_token, _ = security.create_access_token(user_id=user.id)
    assert security.decode_token(access_token, expected_type="access")["sub"] == user.id
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(access_token, expected_type="refresh")
    settings = get_settings()
    expired = jwt.encode({"sub": user.id, "type": "access", "iat": 1, "exp": 2, "jti": "expired"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_token(expired, expected_type="access")
    missing_jti = jwt.encode({"sub": user.id, "type": "access", "iat": int(datetime.now(timezone.utc).timestamp()), "exp": int((datetime.now(timezone.utc) + timedelta(minutes=1)).timestamp())}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.MissingRequiredClaimError):
        security.decode_token(missing_jti, expected_type="access")
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_token(access_token + "x", expected_type="access")


def test_refresh_rotation_replay_detection_and_logout(db: Session) -> None:
    user = _register(db)
    initial = service.issue_token_pair(db, user=user)
    first_refresh = initial["refresh_token"]
    rotated = service.refresh_token_pair(db, raw_refresh_token=first_refresh)
    assert rotated["refresh_token"] != first_refresh
    with pytest.raises(service.RefreshTokenReuseError):
        service.refresh_token_pair(db, raw_refresh_token=first_refresh)
    with pytest.raises(service.RefreshTokenReuseError):
        service.refresh_token_pair(db, raw_refresh_token=rotated["refresh_token"])
    fresh = service.issue_token_pair(db, user=user)
    service.revoke_refresh_token(db, raw_refresh_token=fresh["refresh_token"])
    with pytest.raises(service.RefreshTokenReuseError):
        service.refresh_token_pair(db, raw_refresh_token=fresh["refresh_token"])
    assert db.query(RefreshToken).filter(RefreshToken.token_hash.is_not(None)).count() >= 3


def test_refresh_rejects_expired_and_inactive_sessions(db: Session) -> None:
    user = _register(db)
    token = service.issue_token_pair(db, user=user)["refresh_token"]
    record = RefreshTokenRepository.get_by_hash(db, security.hash_refresh_token(token))
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(service.InvalidRefreshTokenError):
        service.refresh_token_pair(db, raw_refresh_token=token)
    active = service.issue_token_pair(db, user=user)
    UserRepository.set_active(db, user, False)
    with pytest.raises(service.UserInactiveError):
        service.refresh_token_pair(db, raw_refresh_token=active["refresh_token"])

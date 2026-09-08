from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import RefreshToken, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    """Persistence operations for User records."""

    @staticmethod
    def get_by_id(db: Session, user_id: str) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_username(db: Session, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user",
        is_verified: bool = False,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            is_verified=is_verified,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_last_login(db: Session, user: User) -> None:
        user.last_login_at = _utcnow()
        db.commit()

    @staticmethod
    def set_active(db: Session, user: User, active: bool) -> None:
        user.is_active = active
        db.commit()


class RefreshTokenRepository:
    """Persistence operations for RefreshToken records."""

    @staticmethod
    def get_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: str,
        token_hash: str,
        token_family: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            token_family=token_family,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def revoke(
        db: Session,
        record: RefreshToken,
        *,
        replaced_by_token_id: str | None = None,
    ) -> None:
        record.revoked_at = _utcnow()
        record.replaced_by_token_id = replaced_by_token_id
        db.commit()

    @staticmethod
    def revoke_family(db: Session, token_family: str) -> None:
        """
        Revoke every token in a family.

        Used when refresh-token reuse is detected.
        """
        stmt = select(RefreshToken).where(
            RefreshToken.token_family == token_family,
            RefreshToken.revoked_at.is_(None),
        )
        records = db.execute(stmt).scalars().all()

        now = _utcnow()

        for record in records:
            record.revoked_at = now

        db.commit()

    @staticmethod
    def touch_last_used(db: Session, record: RefreshToken) -> None:
        record.last_used_at = _utcnow()
        db.commit()
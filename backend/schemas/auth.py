from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.core.config import get_settings


class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        settings = get_settings()

        if len(value) < settings.min_password_length:
            raise ValueError(
                f"Password must be at least "
                f"{settings.min_password_length} characters long."
            )

        # bcrypt only accepts the first 72 bytes. Reject oversized values
        # instead of silently weakening a user's effective password.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes.")

        # Reject obviously weak passwords.
        if value.lower() in {
            "password",
            "password123",
            "12345678",
            "qwerty123",
            "letmein",
            "admin123",
        }:
            raise ValueError("Password is too weak.")

        return value


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    is_verified: bool


class RegisterResponse(BaseModel):
    id: str
    username: str
    email: str
    message: str = "Registration successful"


class MessageResponse(BaseModel):
    message: str

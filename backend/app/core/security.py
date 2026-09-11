"""Password hashing and JWT issuance/verification.

Uses `bcrypt` directly (not passlib, which has a long-standing compatibility
warning with recent bcrypt releases) and `python-jose` for JWT.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(
    subject: str, expires_delta: timedelta, token_type: Literal["access", "refresh"]
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return cast(str, jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm))


def create_access_token(subject: str) -> str:
    return _create_token(subject, timedelta(minutes=settings.access_token_expire_minutes), "access")


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, timedelta(days=settings.refresh_token_expire_days), "refresh")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return cast(
            dict[str, Any], jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

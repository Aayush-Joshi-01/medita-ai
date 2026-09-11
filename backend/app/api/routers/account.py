"""Registration, login, refresh, and the current-user endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import RefreshRequest, TokenPair, UserCreate, UserLogin, UserRead

router = APIRouter(prefix="/account", tags=["account"])


def _issue_tokens(user: User) -> TokenPair:
    subject = str(user.id)
    return TokenPair(
        access_token=create_access_token(subject), refresh_token=create_refresh_token(subject)
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists is not None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthError("Incorrect email or password")
    if not user.is_active:
        raise AuthError("Account is disabled")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise AuthError("Invalid or expired refresh token") from exc
    if claims.get("type") != "refresh":
        raise AuthError("Invalid token type")

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return _issue_tokens(user)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user

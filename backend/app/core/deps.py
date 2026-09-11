"""Shared FastAPI dependencies: DB session, current user, role guards."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole

__all__ = ["get_db", "get_current_user", "require_role"]

# tokenUrl is informational (drives the Swagger "Authorize" flow); the actual
# route is registered by api/routers/account.py.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/account/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if token is None:
        raise AuthError("Not authenticated")
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise AuthError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise AuthError("Invalid token type")
    user_id = payload.get("sub")
    user = db.get(User, int(user_id)) if user_id is not None else None
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: `Depends(require_role(UserRole.doctor))`."""

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("You do not have access to this resource")
        return user

    return _dependency

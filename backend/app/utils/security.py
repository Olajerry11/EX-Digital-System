# =============================================================================
# EX-DIGITAL — Security Utilities (JWT + bcrypt)
# =============================================================================
# Provides:
#   - Password hashing/verification using bcrypt (direct, not passlib)
#   - JWT creation and decoding with role claims
#   - FastAPI dependency for extracting + validating the current user
#   - RBAC factory: require_role(["admin", "lecturer"])
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =============================================================================
# Password Hashing
# =============================================================================

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt (work factor 12)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of a plain password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# =============================================================================
# JWT Tokens
# =============================================================================

def create_access_token(
    user_id: str | uuid.UUID,
    email: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Standard claims:
        sub  — user UUID as string
        email — user email
        role  — UserRole value
        exp  — expiry timestamp
        iat  — issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT. Raises HTTPException 401 on any failure.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_error
        return payload
    except JWTError:
        raise credentials_error


# =============================================================================
# FastAPI Dependencies
# =============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: extracts JWT → loads and returns the User from the database.
    Raises 401 if token is invalid; 403 if user is inactive.
    """
    payload = decode_access_token(token)
    user_id_str: str = payload["sub"]

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token subject.")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive.")

    return user


def require_role(roles: list[UserRole | str]) -> Any:
    """
    RBAC dependency factory.

    Usage in a route:
        current_user: User = Depends(require_role(["admin"]))
    """
    role_values = [r.value if isinstance(r, UserRole) else r for r in roles]

    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role.value not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(role_values)}.",
            )
        return current_user

    return Depends(_check_role)

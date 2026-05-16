# =============================================================================
# EX-DIGITAL — Auth Router (/auth)
# =============================================================================

from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    BulkUserImportResult,
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.utils.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email OR matric_number + password.
    Returns a signed JWT on success.
    """
    # Build query — support both email and matric number login
    filters = []
    if payload.email:
        filters.append(User.email == str(payload.email).lower())
    if payload.matric_number:
        filters.append(User.matric_number == payload.matric_number.upper())

    result = await db.execute(select(User).where(or_(*filters)))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact your administrator.",
        )

    token = create_access_token(user.id, user.email, user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=str(user.id),
        role=user.role.value,
        full_name=user.full_name,
    )


# ---------------------------------------------------------------------------
# POST /auth/register  (Admin only)
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a new user. Admin-only endpoint."""
    # Check for duplicate email
    dup_check = await db.execute(
        select(User).where(
            or_(
                User.email == str(payload.email).lower(),
                User.matric_number == payload.matric_number
                if payload.matric_number
                else False,
            )
        )
    )
    if dup_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email or matric number already exists.",
        )

    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        full_name=payload.full_name,
        matric_number=payload.matric_number,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""
    return current_user


# ---------------------------------------------------------------------------
# POST /auth/reset-password  (Admin only)
# ---------------------------------------------------------------------------
@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def reset_password(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Admin resets any user's password."""
    result = await db.execute(select(User).where(User.id == payload.user_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return MessageResponse(message=f"Password reset for {user.email}.")


# ---------------------------------------------------------------------------
# POST /auth/bulk-import  (Admin only — CSV upload)
# ---------------------------------------------------------------------------
@router.post(
    "/bulk-import",
    response_model=BulkUserImportResult,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def bulk_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> BulkUserImportResult:
    """
    Bulk-create users from a CSV file.
    Required columns: email, password, full_name, role, matric_number (optional)
    """
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))

    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # Row 1 is header
        try:
            email = row.get("email", "").strip().lower()
            password = row.get("password", "").strip()
            full_name = row.get("full_name", "").strip()
            role_str = row.get("role", "").strip().lower()
            matric = row.get("matric_number", "").strip() or None

            if not email or not password or not full_name or not role_str:
                errors.append(f"Row {i}: Missing required fields.")
                continue

            try:
                role = UserRole(role_str)
            except ValueError:
                errors.append(f"Row {i}: Invalid role '{role_str}'.")
                continue

            # Check for duplicates
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                full_name=full_name,
                matric_number=matric.upper() if matric else None,
            )
            db.add(user)
            created += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")

    await db.commit()
    return BulkUserImportResult(created=created, skipped=skipped, errors=errors)

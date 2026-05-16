# =============================================================================
# EX-DIGITAL — Admin Router (/admin)
# =============================================================================

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AttendanceSession, Course, SessionStatus, User, UserRole
from app.schemas import DashboardStats, MessageResponse, UserListOut, UserOut, UserUpdateRequest
from app.utils.security import get_current_user, require_role

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[require_role([UserRole.ADMIN])],
)


# ---------------------------------------------------------------------------
# GET /admin/dashboard/stats
# ---------------------------------------------------------------------------
@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """Return system-wide statistics for the admin dashboard."""
    # Total users
    total_users_res = await db.execute(select(func.count(User.id)))
    total_users = total_users_res.scalar_one() or 0

    students_res = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.STUDENT)
    )
    total_students = students_res.scalar_one() or 0

    lecturers_res = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.LECTURER)
    )
    total_lecturers = lecturers_res.scalar_one() or 0

    courses_res = await db.execute(
        select(func.count(Course.id)).where(Course.is_archived == False)
    )
    total_courses = courses_res.scalar_one() or 0

    active_sessions_res = await db.execute(
        select(func.count(AttendanceSession.id)).where(
            AttendanceSession.status == SessionStatus.ACTIVE
        )
    )
    active_sessions_today = active_sessions_res.scalar_one() or 0

    return DashboardStats(
        total_users=total_users,
        total_students=total_students,
        total_lecturers=total_lecturers,
        total_courses=total_courses,
        active_sessions_today=active_sessions_today,
        overall_attendance_rate=0.0,  # Computed separately for performance
    )


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------
@router.get("/users", response_model=list[UserListOut])
async def list_users(
    role: UserRole | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    """List all users, optionally filtered by role."""
    query = select(User)
    if role:
        query = query.where(User.role == role)
    result = await db.execute(query.order_by(User.created_at.desc()))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id}
# ---------------------------------------------------------------------------
@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


# ---------------------------------------------------------------------------
# PATCH /admin/users/{user_id}
# ---------------------------------------------------------------------------
@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update a user's profile (name, active status, matric number)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# DELETE /admin/users/{user_id}  (soft delete — deactivate)
# ---------------------------------------------------------------------------
@router.delete("/users/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Soft-delete a user by deactivating their account."""
    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user.is_active = False
    await db.commit()
    return MessageResponse(message=f"User {user.email} has been deactivated.")

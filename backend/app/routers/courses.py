# =============================================================================
# EX-DIGITAL — Courses Router (/courses)
# =============================================================================

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    Course,
    CourseEnrollment,
    CourseLecturer,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas import (
    AssignLecturerRequest,
    CourseAttendanceStats,
    CourseCreate,
    CourseOut,
    CourseUpdate,
    EnrollRequest,
    MessageResponse,
    UserListOut,
)
from app.utils.security import get_current_user, require_role

router = APIRouter(prefix="/courses", tags=["Courses"])


# ---------------------------------------------------------------------------
# GET /courses
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[CourseOut])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Course]:
    """
    Scoped course listing:
    - Admin → all non-archived courses
    - Lecturer → courses they are assigned to
    - Student → courses they are enrolled in
    """
    if current_user.role == UserRole.ADMIN:
        result = await db.execute(
            select(Course).where(Course.is_archived == False).order_by(Course.created_at.desc())
        )
        return list(result.scalars().all())

    elif current_user.role == UserRole.LECTURER:
        result = await db.execute(
            select(Course)
            .join(CourseLecturer, CourseLecturer.course_id == Course.id)
            .where(
                CourseLecturer.user_id == current_user.id,
                Course.is_archived == False,
            )
            .order_by(Course.created_at.desc())
        )
        return list(result.scalars().all())

    else:  # Student
        result = await db.execute(
            select(Course)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(
                CourseEnrollment.user_id == current_user.id,
                Course.is_archived == False,
            )
            .order_by(Course.created_at.desc())
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# POST /courses  (Admin / Lecturer)
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=CourseOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role([UserRole.ADMIN, UserRole.LECTURER])],
)
async def create_course(
    payload: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Course:
    """Create a new course."""
    # Check for duplicate code/term
    dup = await db.execute(
        select(Course).where(
            Course.code == payload.code,
            Course.term == payload.term,
            Course.is_archived == False,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Course '{payload.code}' already exists for term '{payload.term}'.",
        )

    admin_id = current_user.id if current_user.role == UserRole.ADMIN else None
    course = Course(
        code=payload.code,
        title=payload.title,
        term=payload.term,
        created_by_admin_id=admin_id,
    )
    db.add(course)

    # If a lecturer creates a course, auto-assign them
    if current_user.role == UserRole.LECTURER:
        await db.flush()
        assignment = CourseLecturer(course_id=course.id, user_id=current_user.id)
        db.add(assignment)

    await db.commit()
    await db.refresh(course)
    return course


# ---------------------------------------------------------------------------
# GET /courses/{course_id}
# ---------------------------------------------------------------------------
@router.get("/{course_id}", response_model=CourseOut)
async def get_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


# ---------------------------------------------------------------------------
# PATCH /courses/{course_id}  (Admin only)
# ---------------------------------------------------------------------------
@router.patch(
    "/{course_id}",
    response_model=CourseOut,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: AsyncSession = Depends(get_db),
) -> Course:
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(course, field, value)

    await db.commit()
    await db.refresh(course)
    return course


# ---------------------------------------------------------------------------
# POST /courses/{course_id}/enroll  (Admin only)
# ---------------------------------------------------------------------------
@router.post(
    "/{course_id}/enroll",
    response_model=MessageResponse,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def enroll_students(
    course_id: uuid.UUID,
    payload: EnrollRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Bulk-enroll a list of students in a course."""
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found.")

    enrolled_count = 0
    for student_id in payload.student_ids:
        # Check student exists and is a student
        student_res = await db.execute(
            select(User).where(User.id == student_id, User.role == UserRole.STUDENT)
        )
        if not student_res.scalar_one_or_none():
            continue

        # Skip duplicates
        dup = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.user_id == student_id,
            )
        )
        if dup.scalar_one_or_none():
            continue

        db.add(CourseEnrollment(course_id=course_id, user_id=student_id))
        enrolled_count += 1

    await db.commit()
    return MessageResponse(message=f"Enrolled {enrolled_count} student(s).")


# ---------------------------------------------------------------------------
# POST /courses/{course_id}/assign-lecturer  (Admin only)
# ---------------------------------------------------------------------------
@router.post(
    "/{course_id}/assign-lecturer",
    response_model=MessageResponse,
    dependencies=[require_role([UserRole.ADMIN])],
)
async def assign_lecturer(
    course_id: uuid.UUID,
    payload: AssignLecturerRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Assign a lecturer to a course."""
    lecturer_res = await db.execute(
        select(User).where(
            User.id == payload.lecturer_id, User.role == UserRole.LECTURER
        )
    )
    if not lecturer_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lecturer not found.")

    dup = await db.execute(
        select(CourseLecturer).where(
            CourseLecturer.course_id == course_id,
            CourseLecturer.user_id == payload.lecturer_id,
        )
    )
    if dup.scalar_one_or_none():
        return MessageResponse(message="Lecturer already assigned to this course.")

    db.add(CourseLecturer(course_id=course_id, user_id=payload.lecturer_id))
    await db.commit()
    return MessageResponse(message="Lecturer assigned successfully.")


# ---------------------------------------------------------------------------
# GET /courses/{course_id}/attendance/stats
# ---------------------------------------------------------------------------
@router.get("/{course_id}/attendance/stats", response_model=CourseAttendanceStats)
async def course_attendance_stats(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CourseAttendanceStats:
    """Return aggregate attendance statistics for a course."""
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    # Total sessions
    sessions_res = await db.execute(
        select(func.count(AttendanceSession.id)).where(
            AttendanceSession.course_id == course_id,
            AttendanceSession.status == SessionStatus.ENDED,
        )
    )
    total_sessions = sessions_res.scalar_one() or 0

    # Enrolled students
    enrolled_res = await db.execute(
        select(func.count(CourseEnrollment.id)).where(
            CourseEnrollment.course_id == course_id
        )
    )
    total_enrolled = enrolled_res.scalar_one() or 0

    # Average attendance
    avg_rate = 0.0
    if total_sessions > 0 and total_enrolled > 0:
        records_res = await db.execute(
            select(func.count(AttendanceRecord.id))
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .where(AttendanceSession.course_id == course_id)
        )
        total_records = records_res.scalar_one() or 0
        max_possible = total_sessions * total_enrolled
        avg_rate = round((total_records / max_possible) * 100, 2)

    return CourseAttendanceStats(
        course_id=course_id,
        course_code=course.code,
        total_sessions=total_sessions,
        total_enrolled=total_enrolled,
        average_attendance_rate=avg_rate,
    )

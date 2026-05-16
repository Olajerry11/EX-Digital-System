# =============================================================================
# EX-DIGITAL — Sessions Router (/sessions)
# =============================================================================

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import (
    AttendanceSession,
    Course,
    CourseLecturer,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas import (
    AttendanceRecordOut,
    MessageResponse,
    SessionOut,
    SessionStartRequest,
    SessionWithQROut,
)
from app.utils.helpers import generate_session_key, utcnow
from app.utils.security import get_current_user, require_role

settings = get_settings()
router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ---------------------------------------------------------------------------
# POST /sessions/start  (Lecturer)
# ---------------------------------------------------------------------------
@router.post(
    "/start",
    response_model=SessionWithQROut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role([UserRole.LECTURER, UserRole.ADMIN])],
)
async def start_session(
    payload: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Start a new attendance session.
    - Validates that the requesting lecturer is assigned to the course.
    - Prevents starting a second active session for the same course.
    - Returns the session UUID for QR code generation.
    """
    # Verify course exists
    course_res = await db.execute(
        select(Course).where(Course.id == payload.course_id, Course.is_archived == False)
    )
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    # Verify lecturer is assigned (skip for admin)
    if current_user.role == UserRole.LECTURER:
        assignment_res = await db.execute(
            select(CourseLecturer).where(
                CourseLecturer.course_id == payload.course_id,
                CourseLecturer.user_id == current_user.id,
            )
        )
        if not assignment_res.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this course.",
            )

    # Prevent overlapping active sessions for the same course
    overlap_res = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.course_id == payload.course_id,
            AttendanceSession.status == SessionStatus.ACTIVE,
        )
    )
    if overlap_res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="An active session already exists for this course. End it first.",
        )

    duration = payload.duration_minutes or settings.SESSION_DURATION_MINUTES
    now = utcnow()
    qr_id = uuid.uuid4()

    session = AttendanceSession(
        course_id=payload.course_id,
        lecturer_id=current_user.id,
        session_key=generate_session_key(),
        qr_uuid=qr_id,
        start_time=now,
        end_time=now + timedelta(minutes=duration),
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        **SessionOut.model_validate(session).model_dump(),
        "qr_deep_link": f"exdigital://scan/{qr_id}",
    }


# ---------------------------------------------------------------------------
# GET /sessions/active  (Lecturer)
# ---------------------------------------------------------------------------
@router.get(
    "/active",
    response_model=list[SessionWithQROut],
    dependencies=[require_role([UserRole.LECTURER, UserRole.ADMIN])],
)
async def get_active_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return all currently active sessions for the requesting lecturer."""
    if current_user.role == UserRole.ADMIN:
        result = await db.execute(
            select(AttendanceSession).where(AttendanceSession.status == SessionStatus.ACTIVE)
        )
    else:
        result = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.lecturer_id == current_user.id,
                AttendanceSession.status == SessionStatus.ACTIVE,
            )
        )

    sessions = result.scalars().all()
    return [
        {
            **SessionOut.model_validate(s).model_dump(),
            "qr_deep_link": f"exdigital://scan/{s.qr_uuid}",
        }
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/end  (Lecturer)
# ---------------------------------------------------------------------------
@router.post(
    "/{session_id}/end",
    response_model=MessageResponse,
    dependencies=[require_role([UserRole.LECTURER, UserRole.ADMIN])],
)
async def end_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Manually end an active session."""
    res = await db.execute(
        select(AttendanceSession).where(AttendanceSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Only the owning lecturer or an admin can end it
    if current_user.role == UserRole.LECTURER and session.lecturer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot end another lecturer's session.")

    if session.status == SessionStatus.ENDED:
        return MessageResponse(message="Session was already ended.")

    session.status = SessionStatus.ENDED
    session.end_time = utcnow()
    await db.commit()
    return MessageResponse(message="Session ended successfully.")


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/attendees  (Lecturer/Admin) — SSE stream
# ---------------------------------------------------------------------------
@router.get(
    "/{session_id}/attendees",
    response_model=list[AttendanceRecordOut],
)
async def get_attendees(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Return list of attendees for a session (for live polling or SSE)."""
    from app.models import AttendanceRecord

    res = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    return list(res.scalars().all())


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/attendees/stream  (SSE)
# ---------------------------------------------------------------------------
@router.get("/{session_id}/attendees/stream")
async def stream_attendees(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for real-time attendee updates.
    The client receives an updated attendee count every 3 seconds.
    """
    import asyncio
    import json

    from app.models import AttendanceRecord
    from sqlalchemy import func

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            count_res = await db.execute(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.session_id == session_id
                )
            )
            count = count_res.scalar_one() or 0

            records_res = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.session_id == session_id
                ).order_by(AttendanceRecord.timestamp.desc()).limit(50)
            )
            records = records_res.scalars().all()

            data = {
                "total": count,
                "records": [
                    {
                        "student_id": str(r.student_id),
                        "timestamp": r.timestamp.isoformat(),
                        "status": r.status.value,
                        "source": r.source.value,
                    }
                    for r in records
                ],
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

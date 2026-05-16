# =============================================================================
# EX-DIGITAL — Attendance Router (/attendance)
# =============================================================================
# Core of the system: the idempotent rapid-scan endpoint that processes
# batches of offline-queued scans, plus manual marking and personal history.
# =============================================================================

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceSource,
    AttendanceStatus,
    Course,
    CourseEnrollment,
    SessionStatus,
    User,
    UserRole,
)
from app.schemas import (
    AttendanceRecordOut,
    ManualMarkRequest,
    MessageResponse,
    RapidScanRequest,
    RapidScanResponse,
    ScanResultItem,
    StudentAttendanceSummary,
)
from app.utils.helpers import utcnow
from app.utils.security import get_current_user, require_role

settings = get_settings()
router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ---------------------------------------------------------------------------
# POST /attendance/rapid-scan  (Student)
# ---------------------------------------------------------------------------
@router.post(
    "/rapid-scan",
    response_model=RapidScanResponse,
    dependencies=[require_role([UserRole.STUDENT])],
)
async def rapid_scan(
    payload: RapidScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RapidScanResponse:
    """
    Core offline-sync endpoint. Accepts a batch of QR scan events.

    Processing logic per scan:
    1. Look up session by qr_uuid.
    2. Verify session is ACTIVE (auto-expire if past end_time).
    3. Check scan is within the allowed time window.
    4. Verify student is enrolled in the session's course.
    5. Check for duplicate (idempotent — same student + session = skip).
    6. Record attendance with correct on_time / late status.

    Returns a detailed breakdown per scan item.
    """
    results: list[ScanResultItem] = []
    # Track in-batch duplicates to prevent double-processing within one request
    processed_in_batch: set[tuple[uuid.UUID, uuid.UUID]] = set()

    for scan in payload.scans:
        # ── 1. Find the session ────────────────────────────────────────────
        session_res = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.qr_uuid == scan.session_uuid
            )
        )
        session = session_res.scalar_one_or_none()

        if not session:
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="session_not_found",
                    message="No session found for this QR code.",
                )
            )
            continue

        # ── 2. Auto-expire if past end_time ────────────────────────────────
        if session.status == SessionStatus.ACTIVE and session.end_time:
            if utcnow() > session.end_time + timedelta(
                minutes=settings.SESSION_GRACE_PERIOD_MINUTES
            ):
                session.status = SessionStatus.ENDED
                await db.flush()

        if session.status == SessionStatus.ENDED:
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="session_ended",
                    message="This attendance session has ended.",
                )
            )
            continue

        # ── 3. Time window check ───────────────────────────────────────────
        window_start = session.start_time - timedelta(
            minutes=settings.QR_SCAN_WINDOW_MINUTES
        )
        window_end = (session.end_time or session.start_time + timedelta(hours=2)) + timedelta(
            minutes=settings.SESSION_GRACE_PERIOD_MINUTES
        )

        scan_ts = scan.timestamp
        if scan_ts.tzinfo is None:
            from datetime import timezone
            scan_ts = scan_ts.replace(tzinfo=timezone.utc)

        if not (window_start <= scan_ts <= window_end):
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="outside_window",
                    message=f"Scan timestamp is outside the allowed window ({window_start.isoformat()} – {window_end.isoformat()}).",
                )
            )
            continue

        # ── 4. Enrollment check ────────────────────────────────────────────
        enrollment_res = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == session.course_id,
                CourseEnrollment.user_id == current_user.id,
            )
        )
        if not enrollment_res.scalar_one_or_none():
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="not_enrolled",
                    message="You are not enrolled in this course.",
                )
            )
            continue

        # ── 5. Duplicate check (DB + in-batch) ─────────────────────────────
        batch_key = (session.id, current_user.id)
        if batch_key in processed_in_batch:
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="duplicate",
                    message="Duplicate scan in this batch.",
                )
            )
            continue

        existing_res = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == session.id,
                AttendanceRecord.student_id == current_user.id,
            )
        )
        if existing_res.scalar_one_or_none():
            results.append(
                ScanResultItem(
                    session_uuid=scan.session_uuid,
                    timestamp=scan.timestamp,
                    result="duplicate",
                    message="Attendance already recorded for this session.",
                )
            )
            continue

        # ── 6. Determine on_time vs late ───────────────────────────────────
        grace_cutoff = session.start_time + timedelta(
            minutes=settings.SESSION_GRACE_PERIOD_MINUTES
        )
        attendance_status = (
            AttendanceStatus.ON_TIME if scan_ts <= grace_cutoff else AttendanceStatus.LATE
        )

        record = AttendanceRecord(
            session_id=session.id,
            student_id=current_user.id,
            timestamp=scan_ts,
            source=AttendanceSource.OFFLINE_SYNC,
            status=attendance_status,
        )
        db.add(record)
        processed_in_batch.add(batch_key)

        results.append(
            ScanResultItem(
                session_uuid=scan.session_uuid,
                timestamp=scan.timestamp,
                result="accepted",
                message=f"Attendance recorded ({attendance_status.value}).",
            )
        )

    await db.commit()

    # Build summary counters
    counter = {"accepted": 0, "duplicate": 0, "not_enrolled": 0, "errors": 0}
    for r in results:
        if r.result == "accepted":
            counter["accepted"] += 1
        elif r.result == "duplicate":
            counter["duplicate"] += 1
        elif r.result == "not_enrolled":
            counter["not_enrolled"] += 1
        else:
            counter["errors"] += 1

    return RapidScanResponse(
        total=len(results),
        accepted=counter["accepted"],
        duplicates=counter["duplicate"],
        not_enrolled=counter["not_enrolled"],
        errors=counter["errors"],
        results=results,
    )


# ---------------------------------------------------------------------------
# POST /attendance/manual  (Lecturer)
# ---------------------------------------------------------------------------
@router.post(
    "/manual",
    response_model=AttendanceRecordOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role([UserRole.LECTURER, UserRole.ADMIN])],
)
async def manual_mark(
    payload: ManualMarkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttendanceRecord:
    """Manually mark a student present in a session."""
    # Verify session
    session_res = await db.execute(
        select(AttendanceSession).where(AttendanceSession.id == payload.session_id)
    )
    session = session_res.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.status == SessionStatus.ENDED:
        raise HTTPException(status_code=409, detail="Cannot mark attendance in an ended session.")

    # Verify student enrollment
    enrollment_res = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == session.course_id,
            CourseEnrollment.user_id == payload.student_id,
        )
    )
    if not enrollment_res.scalar_one_or_none():
        raise HTTPException(
            status_code=422,
            detail="Student is not enrolled in this course.",
        )

    # Idempotent — skip if already recorded
    existing_res = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == payload.session_id,
            AttendanceRecord.student_id == payload.student_id,
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Attendance already recorded for this student in this session.",
        )

    record = AttendanceRecord(
        session_id=payload.session_id,
        student_id=payload.student_id,
        timestamp=utcnow(),
        source=AttendanceSource.MANUAL,
        status=AttendanceStatus.ON_TIME,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# GET /attendance/my  (Student)
# ---------------------------------------------------------------------------
@router.get(
    "/my",
    response_model=list[StudentAttendanceSummary],
    dependencies=[require_role([UserRole.STUDENT])],
)
async def my_attendance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StudentAttendanceSummary]:
    """Return the student's personal attendance history with percentages."""
    # Get all enrolled courses
    enrollments_res = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.user_id == current_user.id)
    )
    enrollments = enrollments_res.scalars().all()

    summaries: list[StudentAttendanceSummary] = []
    for enrollment in enrollments:
        # Get the course
        course_res = await db.execute(
            select(Course).where(Course.id == enrollment.course_id)
        )
        course = course_res.scalar_one_or_none()
        if not course:
            continue

        # Count total sessions
        total_sessions_res = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.course_id == course.id,
                AttendanceSession.status == SessionStatus.ENDED,
            )
        )
        total_sessions = len(total_sessions_res.scalars().all())

        # Get student's records
        records_res = await db.execute(
            select(AttendanceRecord)
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .where(
                AttendanceSession.course_id == course.id,
                AttendanceRecord.student_id == current_user.id,
            )
            .order_by(AttendanceRecord.timestamp.desc())
        )
        records = records_res.scalars().all()
        attended = len(records)

        percentage = round((attended / total_sessions * 100), 2) if total_sessions > 0 else 0.0

        summaries.append(
            StudentAttendanceSummary(
                course_id=course.id,
                course_code=course.code,
                course_title=course.title,
                total_sessions=total_sessions,
                attended=attended,
                attendance_percentage=percentage,
                records=[AttendanceRecordOut.model_validate(r) for r in records],
            )
        )

    return summaries

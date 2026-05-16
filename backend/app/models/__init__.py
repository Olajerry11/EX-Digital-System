# =============================================================================
# EX-DIGITAL — SQLAlchemy ORM Models
# =============================================================================
# All tables use UUID primary keys (server-generated), UTC timestamps via
# TimestampMixin, and appropriate indexes for query performance.
# =============================================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# =============================================================================
# Enumerations
# =============================================================================

class UserRole(str, PyEnum):
    ADMIN = "admin"
    LECTURER = "lecturer"
    STUDENT = "student"


class SessionStatus(str, PyEnum):
    ACTIVE = "active"
    ENDED = "ended"


class AttendanceSource(str, PyEnum):
    SCAN = "scan"
    MANUAL = "manual"
    OFFLINE_SYNC = "offline_sync"


class AttendanceStatus(str, PyEnum):
    ON_TIME = "on_time"
    LATE = "late"
    DUPLICATE = "duplicate"


# =============================================================================
# Mixin — shared timestamp columns
# =============================================================================

class TimestampMixin:
    """Adds created_at and updated_at columns to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# =============================================================================
# Users
# =============================================================================

class User(TimestampMixin, Base):
    """
    Unified user table handling Admin, Lecturer, and Student roles.
    Students have an optional matric_number; lecturers/admins do not.
    """
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("matric_number", name="uq_users_matric_number"),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum"),
        nullable=False,
    )
    matric_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        "CourseEnrollment", back_populates="student", cascade="all, delete-orphan"
    )
    lectured_courses: Mapped[list["CourseLecturer"]] = relationship(
        "CourseLecturer", back_populates="lecturer", cascade="all, delete-orphan"
    )
    sessions_led: Mapped[list["AttendanceSession"]] = relationship(
        "AttendanceSession", back_populates="lecturer", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email!r} [{self.role}]>"


# =============================================================================
# Courses
# =============================================================================

class Course(TimestampMixin, Base):
    """University course. Can be archived (soft-delete)."""
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("code", "term", name="uq_courses_code_term"),
        Index("ix_courses_is_archived", "is_archived"),
        Index("ix_courses_term", "term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    term: Mapped[str] = mapped_column(String(50), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        "CourseEnrollment", back_populates="course", cascade="all, delete-orphan"
    )
    lecturers: Mapped[list["CourseLecturer"]] = relationship(
        "CourseLecturer", back_populates="course", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["AttendanceSession"]] = relationship(
        "AttendanceSession", back_populates="course", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Course {self.code!r} [{self.term}]>"


# =============================================================================
# Course Enrollments (Student ↔ Course)
# =============================================================================

class CourseEnrollment(Base):
    """Maps students to courses they are enrolled in."""
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_enrollment_course_student"),
        Index("ix_enrollment_course_id", "course_id"),
        Index("ix_enrollment_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship("Course", back_populates="enrollments")
    student: Mapped["User"] = relationship("User", back_populates="enrollments")


# =============================================================================
# Course Lecturers (Lecturer ↔ Course)
# =============================================================================

class CourseLecturer(Base):
    """Maps lecturers to the courses they teach."""
    __tablename__ = "course_lecturers"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_lecturer"),
        Index("ix_course_lecturer_course_id", "course_id"),
        Index("ix_course_lecturer_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship("Course", back_populates="lecturers")
    lecturer: Mapped["User"] = relationship("User", back_populates="lectured_courses")


# =============================================================================
# Attendance Sessions
# =============================================================================

class AttendanceSession(TimestampMixin, Base):
    """
    A time-bounded attendance session started by a lecturer.
    The qr_uuid is embedded in the QR code and used by student scanners.
    """
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("length(session_key) = 6", name="ck_session_key_length"),
        Index("ix_sessions_course_id", "course_id"),
        Index("ix_sessions_lecturer_id", "lecturer_id"),
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_qr_uuid", "qr_uuid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    lecturer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_key: Mapped[str] = mapped_column(String(6), nullable=False)
    qr_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum"),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    course: Mapped["Course"] = relationship("Course", back_populates="sessions")
    lecturer: Mapped["User"] = relationship("User", back_populates="sessions_led")
    records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AttendanceSession {self.session_key!r} [{self.status}]>"


# =============================================================================
# Attendance Records
# =============================================================================

class AttendanceRecord(Base):
    """
    A single attendance event — one per student per session.
    source tracks how it was recorded (scan / manual / offline sync).
    synced_to_erp is updated when the gateway pushes to the ERP system.
    """
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
        Index("ix_attendance_session_id", "session_id"),
        Index("ix_attendance_student_id", "student_id"),
        Index("ix_attendance_synced_to_erp", "synced_to_erp"),
        Index("ix_attendance_timestamp", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource, name="attendance_source_enum"),
        nullable=False,
        default=AttendanceSource.SCAN,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        nullable=False,
        default=AttendanceStatus.ON_TIME,
    )
    synced_to_erp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    session: Mapped["AttendanceSession"] = relationship(
        "AttendanceSession", back_populates="records"
    )
    student: Mapped["User"] = relationship("User", back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"<AttendanceRecord student={self.student_id} session={self.session_id}>"

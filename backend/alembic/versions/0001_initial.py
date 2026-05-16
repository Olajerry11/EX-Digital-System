"""Initial schema — all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-05-16

Creates all six tables:
  users, courses, course_enrollments, course_lecturers,
  attendance_sessions, attendance_records
"""

from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────────
    user_role_enum = postgresql.ENUM(
        "admin", "lecturer", "student", name="user_role_enum", create_type=False
    )
    session_status_enum = postgresql.ENUM(
        "active", "ended", name="session_status_enum", create_type=False
    )
    attendance_source_enum = postgresql.ENUM(
        "scan", "manual", "offline_sync", name="attendance_source_enum", create_type=False
    )
    attendance_status_enum = postgresql.ENUM(
        "on_time", "late", "duplicate", name="attendance_status_enum", create_type=False
    )

    op.execute("CREATE TYPE user_role_enum AS ENUM ('admin', 'lecturer', 'student')")
    op.execute("CREATE TYPE session_status_enum AS ENUM ('active', 'ended')")
    op.execute("CREATE TYPE attendance_source_enum AS ENUM ('scan', 'manual', 'offline_sync')")
    op.execute("CREATE TYPE attendance_status_enum AS ENUM ('on_time', 'late', 'duplicate')")

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "lecturer", "student", name="user_role_enum"), nullable=False),
        sa.Column("matric_number", sa.String(20), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("matric_number", name="uq_users_matric_number"),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # ── courses ────────────────────────────────────────────────────────────────
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("term", sa.String(50), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", "term", name="uq_courses_code_term"),
    )
    op.create_index("ix_courses_is_archived", "courses", ["is_archived"])
    op.create_index("ix_courses_term", "courses", ["term"])

    # ── course_enrollments ─────────────────────────────────────────────────────
    op.create_table(
        "course_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_enrollment_course_student"),
    )
    op.create_index("ix_enrollment_course_id", "course_enrollments", ["course_id"])
    op.create_index("ix_enrollment_user_id", "course_enrollments", ["user_id"])

    # ── course_lecturers ───────────────────────────────────────────────────────
    op.create_table(
        "course_lecturers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("course_id", "user_id", name="uq_course_lecturer"),
    )
    op.create_index("ix_course_lecturer_course_id", "course_lecturers", ["course_id"])
    op.create_index("ix_course_lecturer_user_id", "course_lecturers", ["user_id"])

    # ── attendance_sessions ────────────────────────────────────────────────────
    op.create_table(
        "attendance_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("course_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lecturer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_key", sa.String(6), nullable=False),
        sa.Column("qr_uuid", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("active", "ended", name="session_status_enum"), nullable=False,
                  server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(session_key) = 6", name="ck_session_key_length"),
    )
    op.create_index("ix_sessions_course_id", "attendance_sessions", ["course_id"])
    op.create_index("ix_sessions_lecturer_id", "attendance_sessions", ["lecturer_id"])
    op.create_index("ix_sessions_status", "attendance_sessions", ["status"])
    op.create_index("ix_sessions_qr_uuid", "attendance_sessions", ["qr_uuid"])

    # ── attendance_records ─────────────────────────────────────────────────────
    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source",
                  sa.Enum("scan", "manual", "offline_sync", name="attendance_source_enum"),
                  nullable=False, server_default="scan"),
        sa.Column("status",
                  sa.Enum("on_time", "late", "duplicate", name="attendance_status_enum"),
                  nullable=False, server_default="on_time"),
        sa.Column("synced_to_erp", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )
    op.create_index("ix_attendance_session_id", "attendance_records", ["session_id"])
    op.create_index("ix_attendance_student_id", "attendance_records", ["student_id"])
    op.create_index("ix_attendance_synced_to_erp", "attendance_records", ["synced_to_erp"])
    op.create_index("ix_attendance_timestamp", "attendance_records", ["timestamp"])


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("attendance_sessions")
    op.drop_table("course_lecturers")
    op.drop_table("course_enrollments")
    op.drop_table("courses")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS attendance_status_enum")
    op.execute("DROP TYPE IF EXISTS attendance_source_enum")
    op.execute("DROP TYPE IF EXISTS session_status_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")

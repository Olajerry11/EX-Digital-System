# =============================================================================
# EX-DIGITAL — Pydantic v2 Schemas (Request / Response)
# =============================================================================
# All schemas use strict typing, field_validator for input sanitization,
# and model_config = ConfigDict(from_attributes=True) for ORM compatibility.
# =============================================================================

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models import (
    AttendanceSource,
    AttendanceStatus,
    SessionStatus,
    UserRole,
)

# =============================================================================
# Shared base configs
# =============================================================================

class OrmBase(BaseModel):
    """Base for all response schemas that read from SQLAlchemy ORM objects."""
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Auth Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Accepts email OR matric_number (for students) + password."""
    email: EmailStr | None = Field(default=None, description="User email address")
    matric_number: str | None = Field(
        default=None,
        max_length=20,
        description="Student matric number (alternative to email)",
    )
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_email_or_matric(self) -> "LoginRequest":
        if not self.email and not self.matric_number:
            raise ValueError("Either 'email' or 'matric_number' must be provided.")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    user_id: str
    role: str
    full_name: str


class RegisterRequest(BaseModel):
    """Admin-only: create a new user of any role."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole
    matric_number: str | None = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("matric_number")
    @classmethod
    def validate_matric_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Accepts formats: CS/2020/001, ENG2021001, etc.
        if not re.match(r"^[A-Z0-9/\-]{4,20}$", v.upper()):
            raise ValueError(
                "Matric number must be 4–20 characters, alphanumeric with / or -."
            )
        return v.upper()

    @field_validator("full_name")
    @classmethod
    def no_special_chars_in_name(cls, v: str) -> str:
        if re.search(r"[<>\"'%;()&+]", v):
            raise ValueError("Full name contains invalid characters.")
        return v.strip()

    @model_validator(mode="after")
    def student_requires_matric(self) -> "RegisterRequest":
        if self.role == UserRole.STUDENT and not self.matric_number:
            raise ValueError("Students must have a matric_number.")
        return self


class PasswordResetRequest(BaseModel):
    user_id: uuid.UUID
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit.")
        return v


# =============================================================================
# User Schemas
# =============================================================================

class UserOut(OrmBase):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    matric_number: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListOut(OrmBase):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    matric_number: str | None
    is_active: bool


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    matric_number: str | None = Field(default=None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def no_special_chars(cls, v: str | None) -> str | None:
        if v and re.search(r"[<>\"'%;()&+]", v):
            raise ValueError("Full name contains invalid characters.")
        return v.strip() if v else v


# =============================================================================
# Course Schemas
# =============================================================================

class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    title: str = Field(min_length=3, max_length=255)
    term: str = Field(min_length=3, max_length=50)

    @field_validator("code")
    @classmethod
    def course_code_format(cls, v: str) -> str:
        if not re.match(r"^[A-Z0-9/\- ]{2,20}$", v.upper()):
            raise ValueError("Course code must be 2–20 alphanumeric characters.")
        return v.upper().strip()


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    term: str | None = Field(default=None, max_length=50)
    is_archived: bool | None = None


class CourseOut(OrmBase):
    id: uuid.UUID
    code: str
    title: str
    term: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class EnrollRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class AssignLecturerRequest(BaseModel):
    lecturer_id: uuid.UUID


# =============================================================================
# Session Schemas
# =============================================================================

class SessionStartRequest(BaseModel):
    course_id: uuid.UUID
    duration_minutes: int = Field(default=10, ge=1, le=180)


class SessionOut(OrmBase):
    id: uuid.UUID
    course_id: uuid.UUID
    lecturer_id: uuid.UUID
    session_key: str
    qr_uuid: uuid.UUID
    start_time: datetime
    end_time: datetime | None
    status: SessionStatus
    created_at: datetime


class SessionWithQROut(SessionOut):
    """Extended response that includes the deep-link QR URL."""
    qr_deep_link: str


# =============================================================================
# Attendance Schemas
# =============================================================================

class RapidScanItem(BaseModel):
    """A single scan entry from the offline queue."""
    session_uuid: uuid.UUID
    timestamp: datetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_iso_timestamp(cls, v: object) -> object:
        return v  # Pydantic handles ISO8601 automatically


class RapidScanRequest(BaseModel):
    scans: list[RapidScanItem] = Field(min_length=1, max_length=100)


class ScanResultItem(BaseModel):
    session_uuid: uuid.UUID
    timestamp: datetime
    result: Literal["accepted", "duplicate", "not_enrolled", "session_not_found",
                    "session_ended", "outside_window", "error"]
    message: str


class RapidScanResponse(BaseModel):
    total: int
    accepted: int
    duplicates: int
    not_enrolled: int
    errors: int
    results: list[ScanResultItem]


class ManualMarkRequest(BaseModel):
    session_id: uuid.UUID
    student_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class AttendanceRecordOut(OrmBase):
    id: uuid.UUID
    session_id: uuid.UUID
    student_id: uuid.UUID
    timestamp: datetime
    source: AttendanceSource
    status: AttendanceStatus
    synced_to_erp: bool


class StudentAttendanceSummary(BaseModel):
    course_id: uuid.UUID
    course_code: str
    course_title: str
    total_sessions: int
    attended: int
    attendance_percentage: float
    records: list[AttendanceRecordOut]


# =============================================================================
# Stats Schemas
# =============================================================================

class DashboardStats(BaseModel):
    total_users: int
    total_students: int
    total_lecturers: int
    total_courses: int
    active_sessions_today: int
    overall_attendance_rate: float


class CourseAttendanceStats(BaseModel):
    course_id: uuid.UUID
    course_code: str
    total_sessions: int
    total_enrolled: int
    average_attendance_rate: float


# =============================================================================
# Bulk CSV Upload Schema
# =============================================================================

class BulkUserImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[str]


# =============================================================================
# Generic Responses
# =============================================================================

class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    error: str
    details: list[ErrorDetail] | None = None
    request_id: str | None = None

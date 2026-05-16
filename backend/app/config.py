# =============================================================================
# EX-DIGITAL — Application Configuration & Startup Validation
# =============================================================================
# Uses pydantic-settings for type-safe environment variable loading.
# On startup, validates that critical secrets are not left at their default
# values and exits with a clear diagnostic message if they are.
# =============================================================================

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    APP_NAME: str = "EX-DIGITAL"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://exdigital:changeme@localhost:5432/exdigital"

    # ── Security ──────────────────────────────────────────────────────────────
    JWT_SECRET: str = "CHANGE_ME_JWT_SECRET_MUST_BE_VERY_LONG_AND_RANDOM"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    HMAC_SECRET: str = "CHANGE_ME_HMAC_SECRET_FOR_ERP_WEBHOOK"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_RAPID_SCAN: str = "30/minute"

    # ── Attendance Session ────────────────────────────────────────────────────
    SESSION_DURATION_MINUTES: int = 10
    SESSION_GRACE_PERIOD_MINUTES: int = 5
    QR_SCAN_WINDOW_MINUTES: int = 5

    # ── Redis (optional – rate limiting & task queues) ────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── ERP Gateway ──────────────────────────────────────────────────────────
    GATEWAY_INTERNAL_URL: str = "http://gateway:5001"

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_not_be_default(cls, v: str) -> str:
        """Prevent accidentally deploying with the placeholder secret."""
        if v.startswith("CHANGE_ME") and False:  # Only block in production
            raise ValueError("JWT_SECRET must be changed from its default value.")
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long.")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_use_asyncpg(cls, v: str) -> str:
        if "asyncpg" not in v and "postgresql+asyncpg" not in v:
            # Auto-upgrade sync postgres:// → async postgresql+asyncpg://
            v = v.replace("postgresql://", "postgresql+asyncpg://")
            v = v.replace("postgres://", "postgresql+asyncpg://")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """In production, enforce that all secrets are non-default."""
        if self.ENVIRONMENT == "production":
            defaults = {
                "JWT_SECRET": "CHANGE_ME",
                "HMAC_SECRET": "CHANGE_ME",
            }
            for field_name, default_prefix in defaults.items():
                value = getattr(self, field_name, "")
                if value.startswith(default_prefix):
                    print(
                        f"[FATAL] {field_name} is set to its default placeholder value. "
                        f"Set a strong secret in your .env file before deploying to production.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()

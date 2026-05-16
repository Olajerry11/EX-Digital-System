# =============================================================================
# EX-DIGITAL — FastAPI Application Factory (main.py)
# =============================================================================
# Entry point for the Core API service. Configures:
#   - Lifespan: Alembic upgrade + table creation on startup
#   - CORS for the React frontend
#   - Rate limiting via slowapi
#   - Structured error responses
#   - All routers with versioned prefix
# =============================================================================

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routers import admin, attendance, auth, courses, sessions

settings = get_settings()
logger = logging.getLogger("exdigital")

# =============================================================================
# Rate Limiter
# =============================================================================
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# =============================================================================
# Lifespan — startup & shutdown
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup:
    1. Run Alembic migrations (alembic upgrade head)
    2. Log that the service is ready

    On shutdown:
    3. Dispose the async engine connection pool
    """
    import subprocess
    import sys

    logger.info("EX-DIGITAL Core API starting up...")

    # Run Alembic migrations automatically
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd="/app",  # Docker working directory
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("Alembic migration warning: %s", result.stderr)
        else:
            logger.info("Database migrations applied successfully.")
    except Exception as exc:
        logger.warning("Could not run migrations on startup: %s", exc)
        logger.warning("Ensure Alembic is configured and the database is reachable.")

    logger.info("EX-DIGITAL Core API is ready.")
    yield

    # Cleanup
    from app.database import engine
    await engine.dispose()
    logger.info("Database connection pool disposed. Shutdown complete.")


# =============================================================================
# App Factory
# =============================================================================
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production-grade attendance management system for universities. "
            "Supports QR-code scanning, offline sync, and multi-role RBAC."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    app.add_middleware(SlowAPIMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID middleware ─────────────────────────────────────────────────
    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Any) -> Any:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.4f}s"
        return response

    # ── Validation error handler ──────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": " → ".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation failed",
                "details": details,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # ── Generic error handler ─────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(courses.router)
    app.include_router(sessions.router)
    app.include_router(attendance.router)
    app.include_router(admin.router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    @app.get("/", tags=["System"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }

    return app


# =============================================================================
# WSGI/ASGI Entry Point
# =============================================================================
app = create_app()

# =============================================================================
# EX-DIGITAL — Flask Gateway (HMAC Webhook Receiver)
# =============================================================================
# Lightweight Flask service that:
#   1. Receives signed attendance sync payloads from external ERP systems
#   2. Verifies the HMAC-SHA256 signature with 5-minute timestamp tolerance
#   3. Forwards valid records to the Core FastAPI via internal HTTP
#   4. Acts as an ERP data export endpoint for external consumers
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("exdigital.gateway")


# =============================================================================
# Configuration
# =============================================================================

HMAC_SECRET: str = os.environ.get("HMAC_SECRET", "CHANGE_ME_HMAC_SECRET_FOR_ERP_WEBHOOK")
CORE_API_URL: str = os.environ.get("CORE_API_INTERNAL_URL", "http://backend:8000")
GATEWAY_API_KEY: str = os.environ.get("GATEWAY_API_KEY", "CHANGE_ME_GATEWAY_KEY")
HMAC_TIMESTAMP_TOLERANCE: int = int(os.environ.get("HMAC_TIMESTAMP_TOLERANCE", "300"))  # 5 min


# =============================================================================
# HMAC Verification
# =============================================================================

def verify_hmac(payload_bytes: bytes, signature: str, timestamp_str: str) -> bool:
    """
    Verify HMAC-SHA256 signature.
    Expected signature format: HMAC_SHA256(f"{timestamp}.{raw_body}")
    """
    try:
        ts = int(timestamp_str)
        now_ts = int(time.time())
        if abs(now_ts - ts) > HMAC_TIMESTAMP_TOLERANCE:
            logger.warning("HMAC timestamp too old/new: %d (now: %d)", ts, now_ts)
            return False

        message = f"{timestamp_str}.".encode() + payload_bytes
        expected = hmac.new(HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as exc:
        logger.error("HMAC verification error: %s", exc)
        return False


# =============================================================================
# Flask Application Factory
# =============================================================================

def create_app() -> Flask:
    app = Flask(__name__)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "EX-DIGITAL Gateway", "time": datetime.now(timezone.utc).isoformat()})

    @app.get("/")
    def root():
        return jsonify({"service": "EX-DIGITAL ERP Integration Gateway", "version": "1.0.0"})

    # ── POST /webhook/erp-sync ────────────────────────────────────────────────
    @app.post("/webhook/erp-sync")
    def erp_sync():
        """
        Receive signed attendance sync from ERP system.

        Required headers:
            X-Timestamp: Unix timestamp (seconds)
            X-Signature: HMAC-SHA256 hex digest

        Body (JSON array):
        [
            {
                "session_uuid": "...",
                "student_matric": "CS/2020/001",
                "timestamp": "2026-01-15T09:05:00Z",
                "source": "erp_import"
            }
        ]
        """
        raw_body = request.get_data()
        timestamp_str = request.headers.get("X-Timestamp", "")
        signature = request.headers.get("X-Signature", "")

        if not timestamp_str or not signature:
            return jsonify({"error": "Missing X-Timestamp or X-Signature headers."}), 400

        if not verify_hmac(raw_body, signature, timestamp_str):
            logger.warning("Invalid HMAC signature from %s", request.remote_addr)
            return jsonify({"error": "Invalid signature or timestamp out of tolerance."}), 401

        # Parse body
        try:
            data = request.get_json(force=True)
            if not isinstance(data, list):
                return jsonify({"error": "Body must be a JSON array of sync records."}), 422
        except Exception:
            return jsonify({"error": "Invalid JSON body."}), 400

        if len(data) == 0:
            return jsonify({"message": "No records to sync.", "processed": 0}), 200

        if len(data) > 500:
            return jsonify({"error": "Batch too large. Maximum 500 records per request."}), 413

        # Forward to Core API
        results = _forward_to_core(data)
        return jsonify(results), 200

    # ── GET /erp/attendance-export ────────────────────────────────────────────
    @app.get("/erp/attendance-export")
    def attendance_export():
        """
        ERP-facing endpoint to pull unsynced attendance records from Core API.
        Secured by API key in X-API-Key header.
        """
        api_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(api_key, GATEWAY_API_KEY):
            return jsonify({"error": "Invalid API key."}), 401

        course_id = request.args.get("course_id")
        limit = min(int(request.args.get("limit", "100")), 1000)

        # Fetch from Core API
        try:
            with httpx.Client(base_url=CORE_API_URL, timeout=10.0) as client:
                resp = client.get("/attendance/export", params={"course_id": course_id, "limit": limit})
                if resp.status_code == 200:
                    return jsonify(resp.json()), 200
                return jsonify({"error": f"Core API returned {resp.status_code}"}), 502
        except httpx.RequestError as exc:
            logger.error("Core API unreachable: %s", exc)
            return jsonify({"error": "Core API unreachable.", "detail": str(exc)}), 503

    # ── POST /erp/trigger-sync ────────────────────────────────────────────────
    @app.post("/erp/trigger-sync")
    def trigger_sync():
        """
        Admin-triggered sync: marks all attendance records as synced in Core API.
        Secured by API key.
        """
        api_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(api_key, GATEWAY_API_KEY):
            return jsonify({"error": "Invalid API key."}), 401

        try:
            with httpx.Client(base_url=CORE_API_URL, timeout=30.0) as client:
                resp = client.post("/attendance/mark-synced")
                return jsonify(resp.json()), resp.status_code
        except httpx.RequestError as exc:
            logger.error("Core API unreachable: %s", exc)
            return jsonify({"error": "Core API unreachable.", "detail": str(exc)}), 503

    return app


# =============================================================================
# Internal: Forward ERP data to Core API
# =============================================================================

def _forward_to_core(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Transform ERP sync records and push them to the Core API's rapid-scan endpoint.
    Maps student matric_number → user_id via a Core API lookup (if available),
    or stores for deferred processing.
    """
    accepted = 0
    errors: list[str] = []

    try:
        with httpx.Client(base_url=CORE_API_URL, timeout=15.0) as client:
            resp = client.post("/attendance/erp-import", json=records)
            if resp.status_code in (200, 201):
                result = resp.json()
                accepted = result.get("accepted", 0)
            else:
                errors.append(f"Core API error {resp.status_code}: {resp.text[:200]}")
    except httpx.RequestError as exc:
        logger.error("Failed to forward to Core API: %s", exc)
        errors.append(f"Network error: {str(exc)}")

    return {
        "processed": len(records),
        "accepted": accepted,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Entry Point
# =============================================================================
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("GATEWAY_PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)

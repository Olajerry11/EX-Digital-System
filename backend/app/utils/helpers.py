# =============================================================================
# EX-DIGITAL — Utility Helpers
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import random
import string
from datetime import datetime, timezone


def generate_session_key(length: int = 6) -> str:
    """Generate a random numeric session key (e.g. '483920')."""
    return "".join(random.choices(string.digits, k=length))


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def verify_hmac_signature(
    payload_bytes: bytes,
    signature: str,
    secret: str,
    timestamp_str: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Verify an HMAC-SHA256 signature from the ERP gateway.

    The signing message is: f"{timestamp}.{payload_bytes.decode()}".
    Returns False if the timestamp is outside the tolerance window.
    """
    try:
        ts = int(timestamp_str)
        now_ts = int(utcnow().timestamp())
        if abs(now_ts - ts) > tolerance_seconds:
            return False

        message = f"{timestamp_str}.".encode() + payload_bytes
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False

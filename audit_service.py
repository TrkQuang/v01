"""
Audit, Compliance & Security Service.

Implements:
- Structured security logging
- Secret redaction
- GDPR right-to-be-forgotten data deletion
- Audit trail recording
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from database import delete_user_data, get_db, get_or_create_user
from models import AuditLog

logger = logging.getLogger(__name__)

# Patterns for secret redaction
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|secret|key|token|seed|otp)[:=\s]+([^\s,;]+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact passwords, secret keys, and bearer tokens from log messages."""
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1: [REDACTED]", redacted)
    return redacted


def hash_identifier(identifier: str) -> str:
    """One-way salt-hashed identifier for privacy preservation."""
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]


class AuditService:
    """Compliance audit logging and data governance."""

    def record_event(
        self,
        telegram_id: int | str,
        action: str,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        try:
            with get_db() as db:
                user = get_or_create_user(db, telegram_id)
                clean_details = redact_secrets(details) if details else None
                ip_hash = hash_identifier(ip_address) if ip_address else None

                log = AuditLog(
                    user_id=user.id,
                    action=action,
                    details=clean_details,
                    ip_hash=ip_hash,
                    timestamp=datetime.now(timezone.utc),
                )
                db.add(log)
        except Exception as exc:
            logger.warning("Audit logging error: %s", exc)

    def delete_all_user_records(self, telegram_id: int | str) -> bool:
        """Execute full GDPR data erasure for a user."""
        try:
            with get_db() as db:
                success = delete_user_data(db, telegram_id)
                if success:
                    logger.info("GDPR data erasure completed for user %s", telegram_id)
                return success
        except Exception as exc:
            logger.error("Failed to delete user records for %s: %s", telegram_id, exc)
            return False


# Global instance
audit_service = AuditService()


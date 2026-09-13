"""Writes to the audit_logs table (see backend/models/audit.py): a permanent,
append-only, per-organization trail of who did what, for compliance/
traceability - distinct from the console/file logs in logging_config.py,
which are for debugging and aren't meant to be kept forever or queried by
tenant.

Callers pass an already-open Session and commit it themselves - this only
adds the row, on the same transaction as the change it's recording.
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.audit import AuditLog


def log_audit(
    db: Session,
    *,
    org_id: UUID,
    actor_id: UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    extra_data: Optional[dict[str, Any]] = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        extra_data=extra_data,
    )
    db.add(entry)
    return entry

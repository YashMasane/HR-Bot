from sqlalchemy import Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from backend.db.database import Base
from backend.models.mixins import UUIDPKMixin, utcnow
from sqlalchemy import DateTime


class AuditLog(Base, UUIDPKMixin):
    """Append-only. Nothing here is ever updated or deleted

    Note the Python attribute is `extra_data`, not `metadata`: SQLAlchemy's
    Declarative Base already uses `.metadata` internally (it's where table
    definitions live), so a column literally named `metadata` on a model
    would collide with it. `Column("metadata", ...)` keeps the actual
    Postgres column name as `metadata` while avoiding that collision in Python.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_org_created", "org_id", "created_at"),)

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import KBSourceType
from backend.models.mixins import UUIDPKMixin, TimestampMixin


class KBDocument(Base, UUIDPKMixin, TimestampMixin):
    """The Postgres-side record for a knowledge-base document. The actual
    embedded chunks live in Chroma; this row is what admin screens list/edit,
    and what `chroma_collection` + `department_id` tie the vector rows back to
    for the RBAC-filtered retrieval described in architecture doc section 6.
    """

    __tablename__ = "kb_documents"

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = org-wide document, visible to everyone in the org.
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)

    title = Column(String(255), nullable=False)
    source_type = Column(
        Enum(KBSourceType, name="kb_source_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    storage_path = Column(String(500), nullable=True)
    chroma_collection = Column(String(100), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    uploader = relationship("User")

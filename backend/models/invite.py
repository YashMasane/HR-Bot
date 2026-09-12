from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import UserRole
from backend.models.mixins import UUIDPKMixin, utcnow


class Invite(Base, UUIDPKMixin):
    """An invite is single-use and immutable once issued: re-inviting someone
    creates a *new* row rather than mutating an existing one, so the history of
    every invite attempt (including expired/superseded ones) stays intact.
    """

    __tablename__ = "invites"

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email = Column(String(255), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    role = Column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    # We store a hash of the invite token, never the raw token - same reason we
    # hash passwords: if the DB ever leaks, the tokens inside it shouldn't be
    # directly usable.
    token_hash = Column(String(255), nullable=False, unique=True, index=True)

    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    organization = relationship("Organization")
    department = relationship("Department")
    inviter = relationship("User", foreign_keys=[invited_by])

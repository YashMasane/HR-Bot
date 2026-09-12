import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPKMixin:
    """Gives every model a UUID primary key generated in Python (uuid4).

    We generate the UUID in Python rather than in Postgres (e.g. server_default=
    text("gen_random_uuid()")) so the id is known immediately on the object,
    before it's ever flushed to the database - useful when you need to link
    two new rows together (e.g. an Organization and its first User) inside the
    same transaction, before either has been committed.
    """

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)


class TimestampMixin:
    """created_at / updated_at, kept consistent across every table."""

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

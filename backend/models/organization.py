from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.mixins import UUIDPKMixin, TimestampMixin


class Organization(Base, UUIDPKMixin, TimestampMixin):
    """The tenant boundary. Everything else in the schema hangs off org_id,
    even though v1 only ever has one row here - see architecture doc section 11.
    """

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)

    departments = relationship(
        "Department", back_populates="organization", cascade="all, delete-orphan"
    )
    users = relationship("User", back_populates="organization")

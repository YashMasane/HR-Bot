from sqlalchemy import Column, Enum, String, Text
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import CompanySize, CompanyType, Industry
from backend.models.mixins import UUIDPKMixin, TimestampMixin


class Organization(Base, UUIDPKMixin, TimestampMixin):
    """The tenant boundary. Everything else in the schema hangs off org_id,
    even though v1 only ever has one row here - see architecture doc section 11.
    """

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)

    # Required at signup (see OrganizationCreate) - enough to classify the
    # org from day one without asking a new signup for more than the
    # minimum. Everything below is optional and only ever set/edited later
    # via PATCH /organizations/me (see OrganizationUpdate).
    company_type = Column(
        Enum(CompanyType, name="company_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    industry = Column(
        Enum(Industry, name="industry", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    company_size = Column(
        Enum(CompanySize, name="company_size", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    website = Column(String(255), nullable=True)
    headquarters_location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    contact_phone = Column(String(50), nullable=True)

    departments = relationship(
        "Department", back_populates="organization", cascade="all, delete-orphan"
    )
    # cascade="all, delete-orphan" (not the default "save-update, merge") so
    # that deleting an Organization actually deletes its Users in Python,
    # rather than SQLAlchemy's default one-to-many behavior of trying to
    # UPDATE org_id to NULL first - which would fail outright since org_id
    # is NOT NULL. This also makes SQLAlchemy compute a correct delete
    # order across the whole org (users before departments before the org
    # itself, since users.department_id references departments), instead of
    # depending on the DB's ON DELETE CASCADE - which users.department_id
    # doesn't even have (see migration 5509aff24a37 - no ondelete on that FK).
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")

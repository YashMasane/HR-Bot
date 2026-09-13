from sqlalchemy import Column, DateTime, Enum, String

from backend.db.database import Base
from backend.models.enums import CompanyType, Industry
from backend.models.mixins import UUIDPKMixin, utcnow


class OrganizationSignupRequest(Base, UUIDPKMixin):
    """Holds a not-yet-verified setup-organization submission. Nothing here
    becomes a real Organization/User until the applicant clicks the emailed
    verification link (see POST /auth/verify-email) - this row is the only
    place that data lives until then, and it's deleted once verified.

    The password is hashed immediately on submission (never stored plain,
    even temporarily) so verify-email only needs to move it onto the new
    User row, not re-collect or re-hash it.
    """

    __tablename__ = "organization_signup_requests"

    email = Column(String(255), nullable=False, unique=True, index=True)
    org_name = Column(String(255), nullable=False)
    company_type = Column(
        Enum(CompanyType, name="company_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    industry = Column(
        Enum(Industry, name="industry", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Same hash-not-raw-token approach as Invite.token_hash.
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

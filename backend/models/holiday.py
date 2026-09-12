from sqlalchemy import Column, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from backend.db.database import Base
from backend.models.mixins import UUIDPKMixin


class OrgHoliday(Base, UUIDPKMixin):
    """Org-wide non-working days, used to compute working-day counts for leave
    requests (architecture doc section 14.2, point 4).
    """

    __tablename__ = "org_holidays"
    __table_args__ = (UniqueConstraint("org_id", "date", name="uq_org_holiday_date"),)

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)
    name = Column(String(100), nullable=True)

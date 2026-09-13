from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import LeaveStatus
from backend.models.mixins import UUIDPKMixin, TimestampMixin


class LeaveType(Base, UUIDPKMixin):
    __tablename__ = "leave_types"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_leave_type_org_name"),)

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    # NUMERIC (not FLOAT) because money-like/quota math must never suffer
    # floating-point rounding errors - half-day leave (0.5) needs to stay exact.
    annual_quota = Column(Numeric(5, 2), nullable=False)


class LeaveBalance(Base, UUIDPKMixin):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("user_id", "leave_type_id", "year", name="uq_leave_balance_user_type_year"),
    )

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False)
    year = Column(SmallInteger, nullable=False)
    allocated = Column(Numeric(5, 2), nullable=False)
    used = Column(Numeric(5, 2), nullable=False, default=0)

    leave_type = relationship("LeaveType")


class LeaveRequest(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_leave_request_date_order"),
    )

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    leave_type_id = Column(UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_requested = Column(Numeric(5, 2), nullable=False)

    status = Column(
        Enum(LeaveStatus, name="leave_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=LeaveStatus.PENDING,
    )
    # Resolved once at creation time and never recomputed - see architecture
    # doc section 14.1: keeps request history accurate even if org admins
    # change later. SET NULL (not CASCADE) on delete: this FK points at the
    # approver, not the request's owner (user_id already is) - deleting the
    # approver's account should blank out who approved it, not delete a
    # different employee's leave request out from under them.
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    leave_type = relationship("LeaveType")
    requester = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approver_id])

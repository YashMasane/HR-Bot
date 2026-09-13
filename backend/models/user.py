from sqlalchemy import Boolean, Column, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.database import Base
from backend.models.enums import UserRole
from backend.models.mixins import UUIDPKMixin, TimestampMixin


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    org_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # NULL only for SUPER_ADMIN - enforced in application logic (see rbac service),
    # not a DB constraint, since "role X implies column Y is/isn't null" isn't
    # something a plain CHECK/FK can express cleanly across two columns.
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)

    role = Column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.EMPLOYEE,
    )
    is_active = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="users")
    department = relationship("Department", back_populates="users")

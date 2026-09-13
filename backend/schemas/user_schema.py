from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from backend.models.enums import UserRole


class UserUpdate(BaseModel):
    """Self-service profile edit for PATCH /users/me. Deliberately has no
    `email` field at all - not just excluded from what gets applied - so
    email changes can't slip through here even by accident; role,
    department, org, and is_active are all admin-controlled and equally
    absent, since they're not "your own profile" to begin with.
    """

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    org_id: UUID
    department_id: Optional[UUID] = None
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

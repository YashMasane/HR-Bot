from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

from backend.models.enums import UserRole


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

from uuid import UUID

from pydantic import BaseModel

from backend.models.enums import UserRole


class UserLoginInfo(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    role: UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str
    user: UserLoginInfo


class TokenData(BaseModel):
    user_id: UUID

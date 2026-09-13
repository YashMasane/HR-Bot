from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from backend.models.enums import UserRole


class OrganizationCreate(BaseModel):
    """The one and only self-service entry point into the whole app - see
    architecture doc section 14.1. Everyone after this signs up via invite.
    """

    org_name: str = Field(min_length=1, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)


class InviteCreate(BaseModel):
    email: EmailStr
    role: UserRole
    department_id: Optional[UUID] = None


class InviteResponse(BaseModel):
    """No invite_token field here on purpose: the token is emailed directly
    to the invitee via send_invite_email_task, so the API response - which
    the *inviter* sees - has no reason to also carry a credential meant for
    someone else.
    """

    id: UUID
    email: EmailStr
    role: UserRole
    department_id: Optional[UUID] = None
    expires_at: datetime

    class Config:
        from_attributes = True


class AcceptInvite(BaseModel):
    token: str
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)


class LogoutRequest(BaseModel):
    """Optional: if the client also has a refresh token in hand, it can send
    it along so logout revokes both tokens instead of just the access token
    used to authenticate the /logout call itself.
    """

    refresh_token: Optional[str] = None

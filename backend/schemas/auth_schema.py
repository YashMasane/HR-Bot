from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from backend.models.enums import CompanyType, Industry, UserRole


class OrganizationCreate(BaseModel):
    """The one and only self-service entry point into the whole app - see
    architecture doc section 14.1. Everyone after this signs up via invite.

    Only the fields needed to classify the org and create its first admin
    live here. Everything else (website, size, description, ...) is
    optional and set later via PATCH /organizations/me - see
    schemas/organization_schema.py - so signup stays short.
    """

    org_name: str = Field(min_length=1, max_length=255)
    company_type: CompanyType
    industry: Industry
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)


class OrganizationSignupPending(BaseModel):
    """Response for POST /setup-organization. Nothing has been created yet -
    this just confirms a verification email is on its way.
    """

    email: EmailStr
    message: str = "Verification email sent. Check your inbox to finish setting up your organization."


class VerifyEmailRequest(BaseModel):
    token: str


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

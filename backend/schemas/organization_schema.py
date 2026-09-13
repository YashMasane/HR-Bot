from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.models.enums import CompanySize, CompanyType, Industry


class OrganizationUpdate(BaseModel):
    """Partial update for PATCH /organizations/me - every field optional so
    only what the caller actually sends gets changed. Covers both the
    required-at-signup fields (org_name, company_type, industry, in case
    they were set wrong at signup) and the fields that only ever get set
    here (website, company_size, etc).
    """

    org_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    company_type: Optional[CompanyType] = None
    industry: Optional[Industry] = None
    company_size: Optional[CompanySize] = None
    website: Optional[str] = Field(default=None, max_length=255)
    headquarters_location: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(default=None, max_length=500)
    contact_phone: Optional[str] = Field(default=None, max_length=50)


class OrganizationDeleteRequest(BaseModel):
    """Deleting an org is irreversible and takes every department, user,
    invite, KB doc, etc with it - password re-entry guards against this
    firing from a stray click on a SUPER_ADMIN's authenticated session.
    """

    password: str


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    company_type: CompanyType
    industry: Industry
    company_size: Optional[CompanySize] = None
    website: Optional[str] = None
    headquarters_location: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    contact_phone: Optional[str] = None

    class Config:
        from_attributes = True

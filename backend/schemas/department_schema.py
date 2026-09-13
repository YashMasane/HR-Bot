from uuid import UUID

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DepartmentResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str

    class Config:
        from_attributes = True

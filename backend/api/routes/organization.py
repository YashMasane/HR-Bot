import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, require_roles
from backend.core.security import verify_password
from backend.db.database import get_db
from backend.models.enums import UserRole
from backend.models.organization import Organization
from backend.models.user import User
from backend.schemas.organization_schema import (
    OrganizationDeleteRequest,
    OrganizationResponse,
    OrganizationUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=OrganizationResponse)
def read_my_organization(current_user: User = Depends(get_current_user)):
    return current_user.organization


@router.patch("/me", response_model=OrganizationResponse)
def update_my_organization(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Only SUPER_ADMIN can edit org-level info - it applies to the whole
    tenant, not just the caller's own department.
    """
    organization = (
        db.query(Organization).filter(Organization.id == current_user.org_id).first()
    )

    update_data = payload.model_dump(exclude_unset=True)
    org_name = update_data.pop("org_name", None)
    if org_name is not None:
        organization.name = org_name
    for field, value in update_data.items():
        setattr(organization, field, value)

    db.commit()
    db.refresh(organization)
    logger.info(
        "Organization updated (org_id=%s) by user_id=%s", organization.id, current_user.id
    )
    return organization


@router.delete("/me")
def delete_my_organization(
    payload: OrganizationDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """Irreversible: every department, user, invite, KB doc, leave record,
    etc for this org cascades away with it via ON DELETE CASCADE at the DB
    level (see migration 404636feeec1). Requires re-entering the password so
    this can't fire from a stray click on an already-authenticated session.
    """
    if not verify_password(payload.password, current_user.hashed_password):
        logger.warning(
            "Organization deletion failed: incorrect password (user_id=%s)", current_user.id
        )
        raise HTTPException(status_code=400, detail="Incorrect password.")

    organization = (
        db.query(Organization).filter(Organization.id == current_user.org_id).first()
    )
    org_id = organization.id
    org_name = organization.name
    # Deleting the organization cascades to every row that belongs to it -
    # including current_user itself (Organization.users has
    # cascade="all, delete-orphan") - so anything read off current_user must
    # be captured now, before commit() deletes and expires it.
    deleted_by_user_id = current_user.id
    db.delete(organization)
    db.commit()
    logger.info(
        "Organization deleted (org_id=%s, org_name=%s) by user_id=%s",
        org_id, org_name, deleted_by_user_id,
    )

    return {"msg": f"Organization '{org_name}' and all its data have been permanently deleted."}

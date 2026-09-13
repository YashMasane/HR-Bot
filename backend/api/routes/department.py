import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, require_roles
from backend.db.database import get_db
from backend.models.department import Department
from backend.models.enums import UserRole
from backend.models.user import User
from backend.schemas.department_schema import DepartmentCreate, DepartmentResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Suggested names for the create-department UI to offer as a dropdown,
# across every org. Deliberately NOT enforced - POST /departments still
# accepts any name, so a company with a non-standard team name is never
# blocked. This just gives admins something standard to pick from instead
# of typing from scratch, so similar orgs end up with consistent naming
# rather than "Eng" vs "Engineering" vs "engineering team".
STANDARD_DEPARTMENT_NAMES = [
    "Engineering",
    "Product",
    "Design",
    "Sales",
    "Marketing",
    "Customer Support",
    "Human Resources",
    "Finance",
    "Legal",
    "Operations",
    "Information Technology",
    "Business Development",
    "Procurement",
    "Quality Assurance",
    "Research and Development",
    "Administration",
]


@router.get("/catalog", response_model=List[str])
def list_department_catalog(current_user: User = Depends(get_current_user)):
    """Standardized name suggestions, not this org's actual departments -
    see list_departments below for that. Purely advisory for a create-form
    dropdown; POST /departments accepts any name regardless.
    """
    return STANDARD_DEPARTMENT_NAMES


@router.get("", response_model=List[DepartmentResponse])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any authenticated user can list their org's departments - this is
    what fills the department_id dropdown for POST /auth/invites (SUPER_ADMIN
    or DEPT_ADMIN), and it's harmless read access for anyone else in the org.
    """
    return (
        db.query(Department)
        .filter(Department.org_id == current_user.org_id)
        .order_by(Department.name)
        .all()
    )


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    """SUPER_ADMIN only - departments are org-wide structure, the same tier
    as org profile edits (PATCH /organizations/me), not something a
    DEPT_ADMIN scoped to a single department should be creating more of.
    """
    department = Department(org_id=current_user.org_id, name=payload.name)
    db.add(department)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Department creation failed: duplicate name=%r in org_id=%s",
            payload.name, current_user.org_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A department with this name already exists in your organization.",
        )
    db.refresh(department)
    logger.info(
        "Department created (department_id=%s, name=%r, org_id=%s) by user_id=%s",
        department.id, department.name, department.org_id, current_user.id,
    )
    return department

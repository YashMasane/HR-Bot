import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, require_roles
from backend.db.database import get_db
from backend.models.enums import UserRole
from backend.models.user import User
from backend.schemas.user_schema import UserResponse, UserUpdate
from backend.services.rbac import can_delete_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Anyone can edit their own profile - there's just nothing on
    UserUpdate but full_name (see its docstring for why email isn't there).
    """
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    logger.info("User profile updated (user_id=%s)", current_user.id)
    return current_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
):
    """require_roles(...) above is just the flat "SUPER_ADMIN or DEPT_ADMIN
    at all" check - the finer-grained "can THIS actor delete THIS target"
    decision (department scoping, can't delete SUPER_ADMINs, can't delete
    yourself) lives in can_delete_user(), same split as create_invite/
    can_invite.
    """
    target = (
        db.query(User)
        .filter(User.id == user_id, User.org_id == current_user.org_id)
        .first()
    )
    if target is None:
        logger.warning(
            "User deletion failed: user_id=%s not found in org_id=%s",
            user_id, current_user.org_id,
        )
        raise HTTPException(status_code=404, detail="User not found in your organization.")

    can_delete_user(current_user, target)

    target_email = target.email
    db.delete(target)
    db.commit()
    logger.info(
        "User deleted (target_user_id=%s, target_email=%s) by user_id=%s",
        user_id, target_email, current_user.id,
    )

"""Single source of truth for permission decisions (architecture doc section 5).

The rule from the doc: every feature - invites today, KB/leave scoping later -
checks against the same role + department logic, implemented once here,
rather than each route re-deriving its own version of "can this user do this."

This module holds plain functions with no FastAPI imports, so the actual
permission logic can be unit-tested directly (`can_invite(user, role, dept)`)
without spinning up the app or a database. `backend/api/dependencies.py` is
the thin layer that plugs these into FastAPI's `Depends()`.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from backend.models.enums import UserRole
from backend.models.user import User


def can_invite(inviter: User, target_role: UserRole, target_department_id: Optional[UUID]) -> None:
    """Raises HTTPException if `inviter` is not allowed to create an invite
    for `target_role` scoped to `target_department_id`. Returns None (no
    exception) if the invite is allowed.

    Rules, straight from architecture doc sections 3-5:
    - SUPER_ADMIN accounts are never created via invite - only via the
      one-time org bootstrap - so no one can invite one into existence.
    - SUPER_ADMIN can invite DEPT_ADMIN or EMPLOYEE into any department in
      their own org.
    - DEPT_ADMIN can invite EMPLOYEE only, and only into their own
      department - never another one, never as DEPT_ADMIN/SUPER_ADMIN.
    - EMPLOYEE cannot invite anyone (callers should already be blocked by
      the require_roles(...) dependency before this is even reached, but we
      don't rely on that alone - see the "enforced centrally, never assumed"
      principle from the architecture doc).
    """
    if target_role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPER_ADMIN accounts can only be created via organization signup, not invites.",
        )

    if inviter.role == UserRole.SUPER_ADMIN:
        if target_department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="department_id is required when inviting a DEPT_ADMIN or EMPLOYEE.",
            )
        return

    if inviter.role == UserRole.DEPT_ADMIN:
        if target_role != UserRole.EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only invite employees.",
            )
        if target_department_id != inviter.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only invite into their own department.",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to invite users.",
    )

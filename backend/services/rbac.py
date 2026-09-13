"""Single source of truth for permission decisions (architecture doc section 5).

The rule from the doc: every feature - invites today, KB/leave scoping later -
checks against the same role + department logic, implemented once here,
rather than each route re-deriving its own version of "can this user do this."

This module holds plain functions with no FastAPI imports, so the actual
permission logic can be unit-tested directly (`can_invite(user, role, dept)`)
without spinning up the app or a database. `backend/api/dependencies.py` is
the thin layer that plugs these into FastAPI's `Depends()`.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from backend.models.enums import UserRole
from backend.models.user import User

logger = logging.getLogger(__name__)


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
        logger.warning(
            "can_invite denied: SUPER_ADMIN cannot be invited (inviter_id=%s)", inviter.id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPER_ADMIN accounts can only be created via organization signup, not invites.",
        )

    if inviter.role == UserRole.SUPER_ADMIN:
        if target_department_id is None:
            logger.warning(
                "can_invite denied: missing department_id (inviter_id=%s)", inviter.id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="department_id is required when inviting a DEPT_ADMIN or EMPLOYEE.",
            )
        return

    if inviter.role == UserRole.DEPT_ADMIN:
        if target_role != UserRole.EMPLOYEE:
            logger.warning(
                "can_invite denied: DEPT_ADMIN tried to invite role=%s (inviter_id=%s)",
                target_role, inviter.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only invite employees.",
            )
        if target_department_id != inviter.department_id:
            logger.warning(
                "can_invite denied: DEPT_ADMIN tried to invite outside own department "
                "(inviter_id=%s, inviter_department_id=%s, target_department_id=%s)",
                inviter.id, inviter.department_id, target_department_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only invite into their own department.",
            )
        return

    logger.warning(
        "can_invite denied: role=%s has no invite permission (inviter_id=%s)",
        inviter.role, inviter.id,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to invite users.",
    )


def can_delete_user(actor: User, target: User) -> None:
    """The teardown counterpart to can_invite: same role/department shape,
    opposite direction. Raises HTTPException if `actor` may not delete
    `target`; returns None if the deletion is allowed.

    - Nobody can delete their own account through this endpoint - closing
      one's own access isn't a thing this app supports mid-session, and for
      a SUPER_ADMIN it's inseparable from deleting the org itself (see
      DELETE /organizations/me).
    - SUPER_ADMIN accounts can't be deleted here at all - there is exactly
      one per org (see can_invite above) and it's the org's owner.
    - SUPER_ADMIN can delete any DEPT_ADMIN or EMPLOYEE in their org.
    - DEPT_ADMIN can delete only EMPLOYEE accounts in their own department -
      never another DEPT_ADMIN, never outside their department.
    """
    if target.id == actor.id:
        logger.warning("can_delete_user denied: self-deletion attempt (actor_id=%s)", actor.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    if target.role == UserRole.SUPER_ADMIN:
        logger.warning(
            "can_delete_user denied: SUPER_ADMIN target (actor_id=%s, target_id=%s)",
            actor.id, target.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPER_ADMIN accounts cannot be deleted.",
        )

    if actor.role == UserRole.SUPER_ADMIN:
        return

    if actor.role == UserRole.DEPT_ADMIN:
        if target.role != UserRole.EMPLOYEE:
            logger.warning(
                "can_delete_user denied: DEPT_ADMIN tried to delete role=%s "
                "(actor_id=%s, target_id=%s)",
                target.role, actor.id, target.id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only delete employees.",
            )
        if target.department_id != actor.department_id:
            logger.warning(
                "can_delete_user denied: DEPT_ADMIN tried to delete outside own department "
                "(actor_id=%s, actor_department_id=%s, target_id=%s, target_department_id=%s)",
                actor.id, actor.department_id, target.id, target.department_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department admins may only delete employees in their own department.",
            )
        return

    logger.warning(
        "can_delete_user denied: role=%s has no delete permission (actor_id=%s)",
        actor.role, actor.id,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to delete users.",
    )

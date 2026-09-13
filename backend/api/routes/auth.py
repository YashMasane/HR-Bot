import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from backend.api.dependencies import decode_token, get_current_user, require_roles
from backend.core.config import settings
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    generate_secure_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from backend.db.database import get_db
from backend.models.department import Department
from backend.models.enums import UserRole
from backend.models.invite import Invite
from backend.models.organization import Organization
from backend.models.organization_signup import OrganizationSignupRequest
from backend.models.user import User
from backend.schemas.auth_schema import (
    AcceptInvite,
    InviteCreate,
    InviteResponse,
    LogoutRequest,
    OrganizationCreate,
    OrganizationSignupPending,
    VerifyEmailRequest,
)
from backend.schemas.token_schema import Token
from backend.schemas.user_schema import UserResponse
from backend.services.audit_service import log_audit
from backend.services.rbac import can_invite
from backend.services.token_service import blacklist_token, is_token_blacklisted
from backend.tasks.email_tasks import (
    send_invite_email_task,
    send_verification_email_task,
    send_welcome_email_task,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _issue_tokens(user: User) -> dict:
    """Shared by every route that ends in "log this user in": org bootstrap,
    invite acceptance, and plain login. Keeps the token payload/shape in
    exactly one place.

    Note the JWT subject (`sub`) is the user's UUID, not their email. A
    primary key is the one thing about a row that's guaranteed stable; if we
    ever let users change their email, a token minted with the old email
    would silently stop resolving to the right account.
    """
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@router.post(
    "/setup-organization",
    response_model=OrganizationSignupPending,
    status_code=status.HTTP_202_ACCEPTED,
)
def setup_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    """Step 1 of the ONLY public signup path in the whole API - see
    architecture doc section 14.1. Every other account comes from an invite
    (below). This does NOT create the org or the CEO account yet - it only
    stages the submission and emails a verification link. The org + account
    are created by POST /auth/verify-email once that link is clicked, so an
    unreachable/mistyped official email can never end up owning an org.
    """
    if db.query(User).filter(User.email == payload.email).first():
        logger.warning("Signup rejected: email already registered (email=%s)", payload.email)
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    raw_token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SIGNUP_VERIFICATION_EXPIRE_HOURS)

    # Resubmitting the same email before verifying just replaces the pending
    # request (new token, new expiry) instead of erroring - that doubles as
    # the "resend verification email" path without a separate endpoint.
    pending = db.query(OrganizationSignupRequest).filter(
        OrganizationSignupRequest.email == payload.email
    ).first()
    if pending is None:
        pending = OrganizationSignupRequest(email=payload.email)
        db.add(pending)

    pending.org_name = payload.org_name
    pending.company_type = payload.company_type
    pending.industry = payload.industry
    pending.full_name = payload.full_name
    pending.hashed_password = get_password_hash(payload.password)
    pending.token_hash = hash_token(raw_token)
    pending.expires_at = expires_at
    db.commit()

    # Fire-and-forget, same as invites (see create_invite below): runs on a
    # Celery worker so a slow/down email provider never blocks this request.
    send_verification_email_task.delay(
        to_email=payload.email,
        full_name=payload.full_name,
        org_name=payload.org_name,
        verification_token=raw_token,
    )

    logger.info(
        "Organization signup staged (email=%s, org_name=%s)", payload.email, payload.org_name
    )
    return OrganizationSignupPending(email=payload.email)


@router.post("/verify-email", response_model=Token)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Step 2 of signup: the link from the verification email lands here.
    This is where the org and its first SUPER_ADMIN actually get created -
    setup-organization above only ever staged the submission.
    """
    pending = db.query(OrganizationSignupRequest).filter(
        OrganizationSignupRequest.token_hash == hash_token(payload.token)
    ).first()
    if pending is None:
        logger.warning("Email verification failed: invalid token.")
        raise HTTPException(status_code=400, detail="Invalid verification token.")
    if pending.expires_at < datetime.now(timezone.utc):
        logger.warning("Email verification failed: token expired (email=%s)", pending.email)
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="This verification link has expired. Please sign up again.",
        )
    if db.query(User).filter(User.email == pending.email).first():
        logger.warning(
            "Email verification failed: user already exists (email=%s)", pending.email
        )
        db.delete(pending)
        db.commit()
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    organization = Organization(
        name=pending.org_name,
        company_type=pending.company_type,
        industry=pending.industry,
    )
    db.add(organization)
    # SQLAlchemy's Python-side column `default=` (UUIDPKMixin's default=uuid.uuid4)
    # is evaluated during flush, not at object construction - organization.id
    # is still None right after Organization(...) above. db.flush() sends the
    # pending INSERT to Postgres and populates organization.id, without
    # committing the transaction yet - so if anything below raises, this insert
    # still rolls back along with it. Both rows land in the same transaction.
    db.flush()

    ceo = User(
        org_id=organization.id,
        department_id=None,
        email=pending.email,
        hashed_password=pending.hashed_password,
        full_name=pending.full_name,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db.add(ceo)
    db.delete(pending)
    db.commit()
    db.refresh(ceo)

    logger.info(
        "Organization created (org_id=%s, org_name=%s) with SUPER_ADMIN (user_id=%s, email=%s)",
        organization.id, organization.name, ceo.id, ceo.email,
    )

    # Audit trail rows (separate from the console/file logs above) - kept
    # indefinitely in the DB, queryable per-organization. See audit_service.py.
    log_audit(
        db,
        org_id=organization.id,
        actor_id=ceo.id,
        action="organization_created",
        target_type="organization",
        target_id=organization.id,
        extra_data={"org_name": organization.name},
    )
    log_audit(
        db,
        org_id=organization.id,
        actor_id=ceo.id,
        action="user_created",
        target_type="user",
        target_id=ceo.id,
        extra_data={"email": ceo.email, "role": ceo.role.value},
    )
    db.commit()

    send_welcome_email_task.delay(
        to_email=ceo.email,
        full_name=ceo.full_name,
        org_name=organization.name,
    )

    return _issue_tokens(ceo)


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.DEPT_ADMIN)),
):
    """require_roles(...) above only checks "is this caller a SUPER_ADMIN or
    DEPT_ADMIN at all" - a flat role check. The finer-grained question ("can
    THIS SUPER_ADMIN/DEPT_ADMIN invite THIS role into THIS department") is a
    department-scoping decision, which is exactly what services/rbac.py
    exists for, so it's handled by can_invite(...) below rather than being
    reimplemented inline here.
    """
    can_invite(current_user, payload.role, payload.department_id)

    if payload.department_id is not None:
        department = (
            db.query(Department)
            .filter(Department.id == payload.department_id, Department.org_id == current_user.org_id)
            .first()
        )
        if department is None:
            logger.warning(
                "Invite rejected: department_id=%s not found in org_id=%s",
                payload.department_id, current_user.org_id,
            )
            raise HTTPException(status_code=404, detail="Department not found in your organization.")

    if db.query(User).filter(User.email == payload.email).first():
        logger.warning("Invite rejected: email already registered (email=%s)", payload.email)
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    raw_token = generate_secure_token()
    invite = Invite(
        org_id=current_user.org_id,
        email=payload.email,
        department_id=payload.department_id,
        role=payload.role,
        token_hash=hash_token(raw_token),
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.INVITE_EXPIRE_HOURS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    logger.info(
        "Invite created (invite_id=%s, email=%s, role=%s, department_id=%s) by user_id=%s",
        invite.id, invite.email, invite.role.value, invite.department_id, current_user.id,
    )
    log_audit(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        action="invite_created",
        target_type="invite",
        target_id=invite.id,
        extra_data={
            "invited_email": invite.email,
            "role": invite.role.value,
            "department_id": str(invite.department_id) if invite.department_id else None,
        },
    )
    db.commit()

    # .delay(...) hands this off to a Celery worker and returns immediately -
    # the API responds without waiting on Resend's round trip. If no worker
    # is running, the task just sits queued in Redis until one picks it up;
    # it does NOT fail the request either way.
    send_invite_email_task.delay(
        to_email=invite.email,
        invite_token=raw_token,
        inviter_name=current_user.full_name,
        org_name=current_user.organization.name,
        role=invite.role.value,
    )

    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        department_id=invite.department_id,
        expires_at=invite.expires_at,
    )


@router.post("/accept-invite", response_model=Token)
def accept_invite(payload: AcceptInvite, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token_hash == hash_token(payload.token)).first()
    if invite is None:
        logger.warning("Invite acceptance failed: invalid token.")
        raise HTTPException(status_code=400, detail="Invalid invite token.")
    if invite.accepted_at is not None:
        logger.warning("Invite acceptance failed: already used (invite_id=%s)", invite.id)
        raise HTTPException(status_code=400, detail="This invite has already been used.")
    if invite.expires_at < datetime.now(timezone.utc):
        logger.warning("Invite acceptance failed: expired (invite_id=%s)", invite.id)
        raise HTTPException(status_code=400, detail="This invite has expired.")
    if db.query(User).filter(User.email == invite.email).first():
        logger.warning(
            "Invite acceptance failed: email already registered (email=%s)", invite.email
        )
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    user = User(
        org_id=invite.org_id,
        department_id=invite.department_id,
        email=invite.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=invite.role,
        is_active=True,
    )
    invite.accepted_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "User created via invite (user_id=%s, email=%s, role=%s, org_id=%s)",
        user.id, user.email, user.role.value, user.org_id,
    )
    log_audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        action="user_created",
        target_type="user",
        target_id=user.id,
        extra_data={"email": user.email, "role": user.role.value, "via": "invite"},
    )
    db.commit()

    return _issue_tokens(user)


@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2PasswordRequestForm expects a `username` field - we treat that as
    the email, since this app never had a separate username concept.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Login failed: bad credentials (email=%s)", form_data.username)
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        logger.warning("Login failed: inactive user (email=%s)", form_data.username)
        raise HTTPException(status_code=400, detail="Inactive user")

    logger.info("User logged in (user_id=%s, email=%s)", user.id, user.email)
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        jti: Optional[str] = payload.get("jti")
        if user_id is None or token_type != "refresh" or jti is None:
            raise credentials_exception
        # A blacklisted refresh token here means either it was logged out, or
        # (more interestingly) it was already rotated away by an earlier call
        # to this same endpoint - i.e. someone is replaying an old refresh
        # token. Either way, it doesn't get to mint a new access token.
        if is_token_blacklisted(jti):
            raise credentials_exception
        user = db.query(User).filter(User.id == UUID(user_id)).first()
    except (JWTError, ValueError):
        raise credentials_exception

    if not user or not user.is_active:
        raise credentials_exception

    # Rotate: blacklist the refresh token that was just used, then issue a
    # brand new one. Architecture doc section 8 calls this out explicitly -
    # it limits how long a stolen refresh token stays useful, since
    # presenting it here invalidates it immediately rather than just letting
    # it float around until its own expiry.
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    blacklist_token(jti, exp)

    logger.info("Access token refreshed (user_id=%s)", user.id)
    return _issue_tokens(user)


@router.post("/logout")
def logout(
    body: LogoutRequest = LogoutRequest(),
    payload: dict = Depends(decode_token),
    current_user: User = Depends(get_current_user),
):
    """Revokes the access token used to call this endpoint, and - if the
    client sends one - the refresh token too, so both halves of a session
    can actually be killed instead of just being deleted client-side.
    """
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    blacklist_token(payload["jti"], exp)

    if body.refresh_token:
        try:
            refresh_payload = jwt.decode(
                body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            refresh_jti = refresh_payload.get("jti")
            if refresh_jti:
                blacklist_token(refresh_jti, datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc))
        except JWTError:
            # An already-invalid/garbage refresh token isn't worth failing
            # logout over - the access token is still revoked either way.
            pass

    logger.info("User logged out (user_id=%s)", current_user.id)
    return {"msg": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

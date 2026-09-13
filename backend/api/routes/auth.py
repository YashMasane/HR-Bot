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
    generate_invite_token,
    get_password_hash,
    hash_invite_token,
    verify_password,
)
from backend.db.database import get_db
from backend.models.department import Department
from backend.models.enums import UserRole
from backend.models.invite import Invite
from backend.models.organization import Organization
from backend.models.user import User
from backend.schemas.auth_schema import (
    AcceptInvite,
    InviteCreate,
    InviteResponse,
    LogoutRequest,
    OrganizationCreate,
)
from backend.schemas.token_schema import Token
from backend.schemas.user_schema import UserResponse
from backend.services.rbac import can_invite
from backend.services.token_service import blacklist_token, is_token_blacklisted
from backend.tasks.email_tasks import send_invite_email_task

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


@router.post("/setup-organization", response_model=Token, status_code=status.HTTP_201_CREATED)
def setup_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    """One-time org + CEO account creation. This is the ONLY public signup
    endpoint in the whole API - see architecture doc section 14.1. Every other
    account comes from an invite (below).
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    organization = Organization(name=payload.org_name)
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
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db.add(ceo)
    db.commit()
    db.refresh(ceo)

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
            raise HTTPException(status_code=404, detail="Department not found in your organization.")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    raw_token = generate_invite_token()
    invite = Invite(
        org_id=current_user.org_id,
        email=payload.email,
        department_id=payload.department_id,
        role=payload.role,
        token_hash=hash_invite_token(raw_token),
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.INVITE_EXPIRE_HOURS),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

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
    invite = db.query(Invite).filter(Invite.token_hash == hash_invite_token(payload.token)).first()
    if invite is None:
        raise HTTPException(status_code=400, detail="Invalid invite token.")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invite has already been used.")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This invite has expired.")
    if db.query(User).filter(User.email == invite.email).first():
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

    return _issue_tokens(user)


@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2PasswordRequestForm expects a `username` field - we treat that as
    the email, since this app never had a separate username concept.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

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

    return {"msg": "Successfully logged out."}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

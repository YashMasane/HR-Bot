from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.database import get_db
from backend.models.enums import UserRole
from backend.models.user import User
from backend.schemas.token_schema import TokenData
from backend.services.token_service import is_token_blacklisted

security = HTTPBearer()

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def decode_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Decodes and validates the bearer token: signature, expiry, and now
    also the Redis blacklist. Returns the raw JWT payload (not just the user)
    so callers that need `jti`/`exp` directly - logout, to blacklist the
    token being used to call it - don't have to decode the token a second
    time themselves.
    """
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise _credentials_exception

    jti = payload.get("jti")
    if jti is None or is_token_blacklisted(jti):
        raise _credentials_exception

    return payload


def get_current_user(payload: dict = Depends(decode_token), db: Session = Depends(get_db)) -> User:
    user_id = payload.get("sub")
    if user_id is None:
        raise _credentials_exception
    try:
        token_data = TokenData(user_id=UUID(user_id))
    except ValueError:
        raise _credentials_exception

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise _credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def require_roles(*allowed_roles: UserRole):
    """Dependency factory: `Depends(require_roles(UserRole.SUPER_ADMIN))`.

    This is just the FastAPI wiring - it calls get_current_user (so you get
    both authentication and authorization from one Depends), then checks the
    role against the allowed set. The actual "who's allowed to do what"
    decisions for anything more nuanced than a flat role check (e.g.
    department scoping) live in backend/services/rbac.py, not here.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return dependency

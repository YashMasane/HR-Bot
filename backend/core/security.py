import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt
from backend.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # jti (JWT ID) is a random, unique-per-token identifier. Without it, two
    # tokens minted for the same user within the same second are byte-for-byte
    # identical - HS256 signing is deterministic, and `exp` is only
    # second-precision, so {sub, exp} alone doesn't guarantee uniqueness. That
    # made refresh-token "rotation" meaningless if called twice quickly: the
    # "new" token was literally the same string as the old one. jti also
    # becomes the handle for a future revocation blacklist (see logout()).
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    # Adding a type claim to distinguish it from an access token
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def generate_secure_token() -> str:
    """32 bytes of randomness, URL-safe. This is the raw token that goes in
    an email link (invite, email verification, ...) - it exists only in that
    link, never stored as-is.
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Unlike passwords, these tokens don't need bcrypt's slow, salted
    hashing. Bcrypt earns its cost defending short, human-guessable secrets
    against offline brute force. A token from generate_secure_token() is 256
    bits of randomness - nobody is going to guess it either way. A plain
    SHA-256 hash is enough to make the stored value useless if the DB ever
    leaks, and it's fast enough to look up by (`WHERE token_hash = :hash`),
    which bcrypt deliberately isn't.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

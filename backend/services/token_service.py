"""Redis-backed JWT revocation.

Design: a blacklist, not an allowlist. Every issued token stays valid on its
own (the JWT signature + exp are still what's normally checked) *unless* its
jti shows up here - added only when a token is explicitly killed (logout) or
superseded (refresh rotation). This means issuing a token is a pure, fast,
stateless operation (no Redis write on every login), and Redis only gets
touched for the actions that actually need to invalidate something before its
natural expiry.

We were asked to check *both* access and refresh tokens against this, not
just refresh tokens - meaning every authenticated request now costs one Redis
GET (via is_token_blacklisted, called from get_current_user). That's the
tradeoff being made deliberately: immediate revocation (logout takes effect
on the very next request) over the marginal latency of an extra round trip,
which for a local/managed Redis instance is sub-millisecond.
"""

from datetime import datetime, timezone

from backend.core.redis_client import redis_client

_BLACKLIST_PREFIX = "blacklist:jti:"


def blacklist_token(jti: str, expires_at: datetime) -> None:
    """Marks a token's jti as revoked until its own expiry, then lets Redis
    forget it. There's no point remembering a revoked token past the moment
    it would have expired anyway - the JWT itself will reject it on `exp` by
    then regardless of the blacklist.
    """
    ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl_seconds > 0:
        redis_client.setex(f"{_BLACKLIST_PREFIX}{jti}", ttl_seconds, "1")


def is_token_blacklisted(jti: str) -> bool:
    return redis_client.exists(f"{_BLACKLIST_PREFIX}{jti}") == 1

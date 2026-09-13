import redis

from backend.core.config import settings

# decode_responses=True: get plain Python str back from Redis instead of
# bytes, since everything we store here is just a "1" marker string, not
# binary data.
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

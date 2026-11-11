import hashlib
import re

from functools import lru_cache

import redis
from redis.exceptions import RedisError

from app.database import settings


# Requests per fixed time window.
LIMITS = {
    "login": (10, 60),
    "pos_ip": (1200, 60),
    "pos_terminal": (120, 60),
    "terminal_admin": (30, 60),
}


# Atomic fixed-window counter with automatic expiration.
# Redis executes this entire script as one operation.
RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])

if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end

local ttl = redis.call('TTL', KEYS[1])

if current > tonumber(ARGV[1]) then
    return {0, ttl}
end

return {1, ttl}
"""


class RateLimitUnavailable(Exception):
    pass


@lru_cache(maxsize=8)
def get_redis_client(url: str):
    return redis.Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=2,
        health_check_interval=30,
    )


def safe_identity(value: str) -> str:
    # Avoid storing client identifiers directly in Redis keys.
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def check_limit(
    policy: str,
    identity: str,
) -> tuple[bool, int]:
    maximum, window = LIMITS[policy]

    if not settings.REDIS_URL:
        raise RateLimitUnavailable(
            "Redis rate limiting is not configured"
        )

    key = (
        f"{settings.RATE_LIMIT_PREFIX}:"
        f"{policy}:{safe_identity(identity)}"
    )

    try:
        result = get_redis_client(
            settings.REDIS_URL
        ).eval(
            RATE_LIMIT_SCRIPT,
            1,
            key,
            maximum,
            window,
        )

    except (RedisError, OSError) as error:
        raise RateLimitUnavailable(
            "Rate limiter unavailable"
        ) from error

    allowed, ttl = result
    return bool(allowed), max(1, int(ttl))


def terminal_identity(header_value: str | None):
    """
    Extract only a bounded public terminal identifier.

    Never put the terminal secret in a Redis key.
    """
    if not header_value:
        return None

    match = re.fullmatch(
        r"([1-9][0-9]{0,11})\.[^\s]{1,256}",
        header_value,
    )

    if match is None:
        return None

    return match.group(1)

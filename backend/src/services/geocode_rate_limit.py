"""Per-user rate limit for the typeahead address-search endpoint.

Kept separate from the enriched-valuation limiter (5/hour) — typeahead legitimately
fires ~1 request per few keystrokes. Uses its own Redis key namespace so the
`valuation:enriched:*` scan in valuation_job_store never touches these counters.
"""
from fastapi import HTTPException

from src.config import settings
from src.core.redis import redis_client


def _key(window: str, identifier: str) -> str:
    return f"geosearch:rate:{window}:{identifier}"


async def enforce_search_rate_limit(identifier: str) -> None:
    """Raise 429 if the identifier exceeds the per-minute or per-hour limit."""
    minute_key = _key("minute", identifier)
    hour_key = _key("hour", identifier)

    minute_count = await redis_client.incr(minute_key)
    if minute_count == 1:
        await redis_client.expire(minute_key, 60)
    hour_count = await redis_client.incr(hour_key)
    if hour_count == 1:
        await redis_client.expire(hour_key, 3600)

    if (
        minute_count > settings.geocode_search_rate_limit_minute
        or hour_count > settings.geocode_search_rate_limit_hour
    ):
        raise HTTPException(status_code=429, detail="Too many address searches; slow down.")

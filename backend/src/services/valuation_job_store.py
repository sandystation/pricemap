import json
from typing import Any

from redis import Redis

from src.config import settings
from src.core.redis import redis_client


def _job_key(job_id: str) -> str:
    return f"valuation:enriched:{job_id}"


def _rate_key(scope: str, identifier: str) -> str:
    return f"valuation:enriched:rate:{scope}:{identifier}"


# Deliberately OUTSIDE the "valuation:enriched:*" prefix so count_active_jobs'
# scan does not pick it up and try to JSON-parse an integer counter.
def _global_cap_key() -> str:
    return "valuation:globalcap:day"


async def set_job_status(job_id: str, payload: dict[str, Any]) -> None:
    await redis_client.set(
        _job_key(job_id),
        json.dumps(payload),
        ex=settings.enriched_valuation_ttl_seconds,
    )


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    raw = await redis_client.get(_job_key(job_id))
    return json.loads(raw) if raw else None


async def count_active_jobs() -> int:
    count = 0
    async for key in redis_client.scan_iter(match="valuation:enriched:*"):
        if ":rate:" in key:
            continue
        raw = await redis_client.get(key)
        if not raw:
            continue
        status = json.loads(raw).get("status")
        if status in {"queued", "running"}:
            count += 1
    return count


async def increment_rate_limit(identifier: str) -> tuple[bool, str | None]:
    hour_key = _rate_key("hour", identifier)
    day_key = _rate_key("day", identifier)

    hour_count = await redis_client.incr(hour_key)
    if hour_count == 1:
        await redis_client.expire(hour_key, 3600)

    day_count = await redis_client.incr(day_key)
    if day_count == 1:
        await redis_client.expire(day_key, 86400)

    if hour_count > settings.valuation_rate_limit_hour:
        return False, (
            f"Rate limit exceeded: {settings.valuation_rate_limit_hour} "
            "enriched valuations per hour"
        )
    if day_count > settings.valuation_rate_limit_day:
        return False, (
            f"Rate limit exceeded: {settings.valuation_rate_limit_day} "
            "enriched valuations per day"
        )
    return True, None


async def check_global_daily_cap() -> tuple[bool, str | None]:
    """Enforce a global daily ceiling on accepted enriched valuations.

    Independent of client identity, so it bounds total paid Gemini/Nominatim
    spend even if per-client rate limiting is evaded (e.g. via spoofed headers).
    Call this only AFTER the per-client limit passes, so requests rejected by the
    per-client limit do not consume the global budget.
    """
    key = _global_cap_key()
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 86400)
    if count > settings.valuation_global_daily_cap:
        return False, "Daily enriched-valuation capacity reached. Please try again tomorrow."
    return True, None


async def release_abuse_budget(identifier: str) -> None:
    """Give back one unit of per-client + global budget when an already-counted
    request fails to enqueue (so a broker outage doesn't permanently eat quota).
    Counters floor at 0; best-effort (never raises)."""
    keys = (_rate_key("hour", identifier), _rate_key("day", identifier), _global_cap_key())
    for key in keys:
        try:
            current = await redis_client.get(key)
            if current is not None and int(current) > 0:
                await redis_client.decr(key)
        except (ValueError, TypeError):
            continue


def set_job_status_sync(job_id: str, payload: dict[str, Any]) -> None:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.set(
            _job_key(job_id),
            json.dumps(payload),
            ex=settings.enriched_valuation_ttl_seconds,
        )
    finally:
        client.close()

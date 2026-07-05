"""Product analytics (PostHog) + error tracking (Sentry) helpers.

Everything here is best-effort: telemetry must never block or break a valuation.
All external calls are wrapped in try/except, and both integrations are no-ops
when their keys/DSN are unset (so local/dev runs need no configuration).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_posthog: Any = None
_posthog_init = False


def _get_posthog() -> Any:
    global _posthog, _posthog_init
    if _posthog_init:
        return _posthog
    _posthog_init = True
    from src.config import settings

    if settings.posthog_key:
        try:
            from posthog import Posthog

            _posthog = Posthog(
                project_api_key=settings.posthog_key,
                host=settings.posthog_host,
                # A worker task is short; flush promptly so events aren't lost.
                flush_at=1,
                flush_interval=0.5,
            )
        except Exception:
            logger.exception("PostHog init failed")
            _posthog = None
    return _posthog


def capture_event(
    distinct_id: str,
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Fire a product-analytics event. Never raises."""
    client = _get_posthog()
    if client is None:
        return
    try:
        client.capture(distinct_id=distinct_id, event=event, properties=properties or {})
    except Exception:
        logger.warning("PostHog capture failed for event %s", event, exc_info=True)


def init_sentry(component: str) -> None:
    """Initialize Sentry for a process (api / worker). No-op without a DSN.

    sentry-sdk auto-enables its FastAPI/Starlette and Celery integrations when
    those packages are importable, so a bare init instruments both processes.
    """
    from src.config import settings

    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        sentry_sdk.set_tag("component", component)
    except Exception:
        logger.exception("Sentry init failed")

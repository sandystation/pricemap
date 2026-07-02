from src.config import settings

try:
    from celery import Celery
except ModuleNotFoundError:
    Celery = None


class _MissingCeleryApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            def delay(*_args, **_kwargs):
                raise RuntimeError("Celery is not installed in this environment")

            func.delay = delay
            return func

        return decorator


if Celery is None:
    celery_app = _MissingCeleryApp()
else:
    celery_app = Celery(
        "pricemap",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["src.tasks.valuation"],
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

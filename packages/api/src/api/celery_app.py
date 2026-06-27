from celery import Celery
from common.config import settings

app = Celery(
    "equitie",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["api.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

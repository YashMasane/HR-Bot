from celery import Celery

from backend.core.config import settings
from backend.core.logging_config import setup_logging

setup_logging()

celery_app = Celery(
    "hr_bot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)

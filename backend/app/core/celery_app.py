"""Celery application and task configuration for background automation"""

import os

from celery import Celery

from app.core.config import settings

# In test mode or when celery_always_eager is set, run tasks synchronously
is_test = settings.ENVIRONMENT == "test" or os.environ.get("ENVIRONMENT") == "test"

celery_app = Celery(
    "sfbm_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_always_eager=is_test,  # Eagerly execute in test mode
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
)

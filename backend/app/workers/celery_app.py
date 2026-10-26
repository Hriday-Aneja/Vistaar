from celery import Celery

from app.config import get_settings

settings = get_settings()

celery = Celery("vistaar", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])

celery.conf.beat_schedule = {
    "monitor-pulse-hourly": {"task": "app.workers.tasks.monitor_pulse", "schedule": 3600.0},
}

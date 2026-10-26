from datetime import date

from sqlalchemy import select

from app.workers.celery_app import celery


@celery.task
def monitor_pulse() -> int:
    """Hourly: count Mohalla Pulse alerts across all shops (TODO: push notifications)."""
    from app.db.models import Shop
    from app.db.session import SessionLocal
    from app.services.pulse import pulse_for

    with SessionLocal() as db:
        return sum(len(pulse_for(db, s, date.today())["alerts"]) for s in db.scalars(select(Shop)))


@celery.task
def monitor_sales() -> str:
    """TODO: detect unusual sales drops per merchant and push an alert."""
    return "ok"

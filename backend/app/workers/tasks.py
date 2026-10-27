from datetime import date

from sqlalchemy import select

from app.workers.celery_app import celery


@celery.task
def monitor_pulse() -> int:
    """Hourly: find Mohalla Pulse alerts for every shop, save the new ones (PulseAlert) and push each one live
    to alerts:{shop_id}. Returns how many alerts were found, as before."""
    from app.db.models import Shop
    from app.db.session import SessionLocal
    from app.services.alerts import record_pulse_alerts
    from app.services.pulse import pulse_for

    found = 0
    with SessionLocal() as db:
        for shop in db.scalars(select(Shop)).all():
            alerts = pulse_for(db, shop, date.today())["alerts"]
            found += len(alerts)
            record_pulse_alerts(db, shop, alerts)
    return found


@celery.task
def monitor_sales() -> int:
    """Daily: find shops whose sales have dropped and push a sales-drop alert live to alerts:{shop_id}.
    Returns how many shops have a drop, as before."""
    from app.db.models import Shop
    from app.db.session import SessionLocal
    from app.services.alerts import publish_sales_drop
    from app.services.sales_drop import sales_drop_for

    dropping = 0
    with SessionLocal() as db:
        for shop in db.scalars(select(Shop)).all():
            result = sales_drop_for(db, shop, date.today())
            if result["drop"]:
                dropping += 1
                publish_sales_drop(shop, result)
    return dropping

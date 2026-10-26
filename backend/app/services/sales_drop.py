"""DB side of the sales-drop alert. Today is left out: the owner may not have entered today's sales yet."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Sale, Shop
from app.services.drop_stats import MIN_BASELINE_DAYS, RECENT_DAYS, detect_drop
from app.services.pulse_stats import WINDOW_DAYS


def sales_drop_for(db: Session, shop: Shop, today: date) -> dict:
    last = today - timedelta(days=1)
    since = datetime.combine(today - timedelta(days=WINDOW_DAYS - 1), time.min)
    until = datetime.combine(today, time.min)
    day = func.date(Sale.sold_at)
    rows = db.execute(
        select(day, func.sum(Sale.qty))
        .where(Sale.shop_id == shop.id, Sale.sold_at >= since, Sale.sold_at < until)
        .group_by(day)
    ).all()
    totals = {str(d)[:10]: q for d, q in rows}
    series: list[float] = []
    if totals:
        cursor = date.fromisoformat(min(totals))
        while cursor <= last:
            series.append(totals.get(cursor.isoformat(), 0))
            cursor += timedelta(days=1)

    needed = RECENT_DAYS + MIN_BASELINE_DAYS
    drop = detect_drop(series)
    if len(series) < needed:
        message = f"Abhi itna data nahi hai. Kam se kam {needed} din ki bikri chahiye."
    elif drop is None:
        message = "Bikri aam ke hisaab se chal rahi hai."
    else:
        message = "Bikri aam se kaafi kam ho gayi hai."
    return {"drop": drop, "through": last.isoformat(), "days_of_data": len(series), "message": message}
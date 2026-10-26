from datetime import date, datetime, time, timedelta
from math import ceil
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EventCalendar, Product, Sale, Shop
from app.services.geo import nearby
from app.services.inventory import stock_on_hand
from app.services.pulse_stats import RECENT_DAYS, WINDOW_DAYS, detect_spike
from app.services.worlds import same_world
from app.tuning import NEARBY_RADIUS_KM

TARGET_COVER_DAYS = 5


def _daily_series(days: dict, today: date) -> list[float]:
    start = today - timedelta(days=WINDOW_DAYS - 1)
    first = min(date.fromisoformat(d) for d in days)
    cursor, series = max(start, first), []
    while cursor <= today:
        series.append(days.get(cursor.isoformat(), 0))
        cursor += timedelta(days=1)
    return series


def _load_sales(db: Session, shop_ids: list[int], today: date) -> dict:
    since = datetime.combine(today - timedelta(days=WINDOW_DAYS - 1), time.min)
    day = func.date(Sale.sold_at)
    rows = db.execute(
        select(Sale.shop_id, Sale.product_id, day, func.sum(Sale.qty))
        .where(Sale.shop_id.in_(shop_ids), Sale.sold_at >= since)
        .group_by(Sale.shop_id, Sale.product_id, day)
    ).all()
    grouped: dict = {}
    for shop_id, product_id, d, qty in rows:
        grouped.setdefault((shop_id, product_id), {})[str(d)[:10]] = qty
    return grouped


def pulse_for(db: Session, shop: Shop, today: date) -> dict:
    neighbours = nearby(shop, same_world(db, shop), NEARBY_RADIUS_KM)
    if not neighbours:
        return {"alerts": [], "message": f"Aas-paas {NEARBY_RADIUS_KM:g} km me abhi koi aur Vistaar dukaan nahi judi hai."}

    group_ids = [shop.id] + [s.id for s, _ in neighbours]
    sales = _load_sales(db, group_ids, today)
    series_by_key = {key: _daily_series(days, today) for key, days in sales.items()}

    spikes: dict[int, dict[int, dict]] = {}
    for (shop_id, product_id), series in series_by_key.items():
        spike = detect_spike(series)
        if spike:
            spikes.setdefault(product_id, {})[shop_id] = spike

    events = db.scalars(select(EventCalendar).where(EventCalendar.start_date <= today,
                                                    EventCalendar.end_date >= today,
                                                    EventCalendar.is_demo == shop.is_demo)).all()
    alerts = []
    for product_id, by_shop in spikes.items():
        if len(by_shop) < 2:
            continue
        product = db.get(Product, product_id)
        mine = by_shop.get(shop.id)
        series = series_by_key.get((shop.id, product_id))
        if mine is None and (not series or mean(series[:-RECENT_DAYS] or [0]) <= 0):
            continue
        uplift = round(mean(s["uplift"] for s in by_shop.values()), 1)
        expected = mine["recent"] if mine else mean(series[:-RECENT_DAYS]) * uplift
        stock = stock_on_hand(db, shop.id, product_id)
        cover = round(stock / expected, 1) if expected > 0 else None
        need = max(0, ceil(expected * TARGET_COVER_DAYS - stock))
        event = next((e for e in events if product.category in e.categories), None)

        cause_text = f"Karan: {event.label}." if event else "Karan abhi pata nahi, par paas ki dukaanon me ek saath bikri badhi hai."
        where = "aapki dukaan samet " if mine else ""
        action = (f"{need} {product.name} aur rakho." if need > 0 else "Aapka stock abhi theek hai.")
        why = (f"{where}{len(by_shop)} dukaan me {product.name} ki bikri {uplift}x badhi hai. {cause_text} "
               f"Aapke paas {cover} din ka stock bacha hai.")
        alerts.append({
            "product_id": product_id, "product": product.name, "category": product.category,
            "shops_spiking": len(by_shop), "includes_me": mine is not None, "uplift": uplift,
            "max_z": max(s["z"] for s in by_shop.values()),
            "cause": ({"kind": event.kind, "label": event.label} if event else None),
            "event_action": event.suggested_action if event else None,
            "stock": stock, "expected_daily": round(expected, 1), "cover_days": cover,
            "suggested_qty": need, "action": action, "why": why,
        })
    alerts.sort(key=lambda a: a["uplift"], reverse=True)
    message = None if alerts else "Abhi paas ki dukaanon me ek saath bikri ka uchhaal nahi dikha."
    return {"alerts": alerts, "message": message}
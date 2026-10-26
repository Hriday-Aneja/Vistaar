from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tuning import FORECAST_WINDOW_DAYS
from app.db.models import Batch, Sale


def daily_rate(db: Session, shop_id: int, product_id: int, today, window_days: int = FORECAST_WINDOW_DAYS) -> float:
    start = datetime.combine(today - timedelta(days=window_days - 1), datetime.min.time())
    total = db.scalar(
        select(func.coalesce(func.sum(Sale.qty), 0)).where(
            Sale.shop_id == shop_id, Sale.product_id == product_id, Sale.sold_at >= start
        )
    )
    return round(total / window_days, 2)


def stock_on_hand(db: Session, shop_id: int, product_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(Batch.qty_left), 0)).where(
            Batch.shop_id == shop_id, Batch.product_id == product_id
        )
    )


def days_of_cover(stock: int, rate: float):
    return round(stock / rate, 1) if rate > 0 else None

from datetime import date, timedelta
from typing import Optional

from app.tuning import INFERENCE_HORIZON_DAYS


def effective_expiry(expiry_date: Optional[date], expiry_source: str, received_on: date, default_shelf_days: int):
    if expiry_date is not None:
        return expiry_date, expiry_source
    return received_on + timedelta(days=default_shelf_days), "default"


def assess(qty_left: int, daily_rate: float, today: date, expiry_date: Optional[date] = None,
           received_on: Optional[date] = None, horizon_days: int = INFERENCE_HORIZON_DAYS) -> dict:
    inferred = expiry_date is None
    if inferred:
        age = (today - received_on).days if received_on else 0
        days_left = max(horizon_days - age, 0)
    else:
        days_left = (expiry_date - today).days

    sellable = daily_rate * max(days_left, 0)
    at_risk = max(0, round(qty_left - sellable))
    days_to_sell = round(qty_left / daily_rate, 1) if daily_rate > 0 else None

    if qty_left <= 0:
        level = "none"
    elif days_left < 0:
        level = "expired"
    elif at_risk >= 0.5 * qty_left:
        level = "high"
    elif at_risk > 0:
        level = "medium"
    else:
        level = "low"

    rate_text = f"roz ~{daily_rate:.1f} bik rahe hain" if daily_rate > 0 else "bikri nahi ho rahi"
    if inferred:
        when = f"{days_left} din ka andaaza (expiry nahi di)"
    elif days_left < 0:
        when = f"{-days_left} din pehle expire ho chuka"
    else:
        when = f"{days_left} din me expiry"
    why = f"{qty_left} bache hain, {rate_text}, {when}."
    if at_risk > 0 and level != "expired":
        why += f" Lagbhag {at_risk} bik nahi payenge."

    return {"level": level, "days_left": days_left, "at_risk_qty": at_risk,
            "days_to_sell": days_to_sell, "inferred": inferred, "why": why}

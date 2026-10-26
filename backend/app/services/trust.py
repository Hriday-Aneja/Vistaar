from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Customer, KhataEntry, Shop
from app.services.privacy import PRIVACY_LABEL, bucket_count, noisy_amount, noisy_days
from app.services.trust_scoring import score_risk, suggested_limit

MIN_OTHER_SHOPS = 2  # never show a cross-shop score built from fewer than this many other shops


def shop_stats(db: Session, shop_id: int, customer_id: int, today: date) -> dict:
    entries = db.scalars(select(KhataEntry).where(KhataEntry.shop_id == shop_id,
                                                  KhataEntry.customer_id == customer_id)).all()
    credit = sum(e.amount for e in entries if e.amount > 0)
    paid = -sum(e.amount for e in entries if e.amount < 0)
    pending = round(credit - paid, 2)
    payments = [e.created_on for e in entries if e.amount < 0]
    credits = [e.created_on for e in entries if e.amount > 0]
    anchor: Optional[date] = max(payments) if payments else (min(credits) if credits else None)
    overdue = (today - anchor).days if pending > 0 and anchor else 0
    return {"credit": credit, "paid": paid, "pending": pending, "overdue_days": overdue}


def network_view(db: Session, shop: Shop, customer: Customer, today: date) -> dict:
    rows = db.execute(
        select(Customer, Shop).join(Shop, Customer.shop_id == Shop.id)
        .where(Customer.phone_hash == customer.phone_hash, Customer.shop_id != shop.id)
    ).all()
    others = [shop_stats(db, c.shop_id, c.id, today) for c, s in rows if s.is_demo == shop.is_demo]
    base = {"privacy": PRIVACY_LABEL, "shops_seen": bucket_count(len(others))}
    if len(others) < MIN_OTHER_SHOPS:
        return {**base, "status": "not_enough_data", "level": None, "suggested_limit": None, "room_left": None,
                "reasons": [], "message": "Is customer ka network data abhi kam hai, isliye risk nahi bata sakte."}

    day = today.isoformat()
    key = customer.phone_hash
    credit = noisy_amount(sum(o["credit"] for o in others), key, "credit", day)
    paid = noisy_amount(sum(o["paid"] for o in others), key, "paid", day)
    pending = noisy_amount(sum(o["pending"] for o in others), key, "pending", day)
    overdue = noisy_days(max(o["overdue_days"] for o in others), key, "overdue", day)
    ratio = min(1.0, paid / credit) if credit > 0 else 1.0

    own_pending = shop_stats(db, shop.id, customer.id, today)["pending"]
    score, level, reasons = score_risk(ratio, overdue, pending)
    limit, room = suggested_limit(score, pending, own_pending)
    return {**base, "status": "ok", "level": level, "score": score, "suggested_limit": limit, "room_left": room,
            "reasons": reasons, "message": None}

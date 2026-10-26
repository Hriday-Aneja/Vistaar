"""Distributor Fair-Price Radar: compare live quotes with what other pools actually paid."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Distributor, DistributorQuote, Product, User
from app.db.session import get_db
from app.deps import current_user
from app.services.bulk import paid_price_history
from app.services.price_radar import benchmark, flag_quote, run_reverse_auction

router = APIRouter(prefix="/api/prices", tags=["price-radar"])


@router.get("/radar")
def radar(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    world = user.shop.is_demo
    out = []
    for product in db.scalars(select(Product).order_by(Product.name)):
        rows = db.execute(
            select(DistributorQuote, Distributor).join(Distributor, DistributorQuote.distributor_id == Distributor.id)
            .where(DistributorQuote.product_id == product.id, DistributorQuote.valid_till >= today,
                   Distributor.is_demo == world)
        ).all()
        if not rows:
            continue
        bench = benchmark(paid_price_history(db, product.id, demo=world))
        offers = {str(q.distributor_id): q.unit_price for q, _ in rows}
        floors = {str(q.distributor_id): round(q.unit_price * d.floor_ratio, 2) for q, d in rows}
        final, events = run_reverse_auction(offers, floors)
        out.append({
            "product_id": product.id, "product": product.name, "mrp": product.mrp, "benchmark": bench,
            "quotes": [{"distributor": d.name, "unit_price": q.unit_price, "min_qty": q.min_qty,
                        "delivery_days": q.delivery_days, "flag": flag_quote(q.unit_price, bench),
                        "after_auction": final[str(q.distributor_id)]} for q, d in rows],
            "auction_rounds": events,
        })
    return out
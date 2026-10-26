"""Impact numbers for the logged-in shop: bulk-buy savings, shops pooled, udhaar recovered, expiry stock moved."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Batch, KhataEntry, Product, PurchaseOrder, Swap, User
from app.db.session import get_db
from app.deps import current_user
from app.services.geo import nearby
from app.services.worlds import same_world
from app.tuning import NEARBY_RADIUS_KM, SOLO_PRICE_RATIO

router = APIRouter(prefix="/api/impact", tags=["impact"])

RECENT_DAYS = 30


@router.get("")
def impact(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    me = user.shop
    mrp = {p.id: p.mrp for p in db.scalars(select(Product))}

    # Bulk-buy: this shop's own lines on approved orders it placed (seed history is excluded).
    orders, saved, spent = 0, 0.0, 0.0
    for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.status == "approved",
                                                     PurchaseOrder.thread_id != "seed")):
        mine = [ln for ln in po.lines if ln["shop_id"] == me.id]
        if not mine:
            continue
        orders += 1
        for ln in mine:
            spent += ln["qty"] * ln["unit_price"]
            saved += ln["qty"] * (mrp.get(ln["product_id"], 0) * SOLO_PRICE_RATIO - ln["unit_price"])

    shops_pooled = 1 + len(nearby(me, same_world(db, me), NEARBY_RADIUS_KM))

    # Udhaar: payments are negative entries, credit given is positive.
    since = date.today() - timedelta(days=RECENT_DAYS)
    entries = db.scalars(select(KhataEntry).where(KhataEntry.shop_id == me.id)).all()
    recovered_all = -sum(e.amount for e in entries if e.amount < 0)
    recovered_recent = -sum(e.amount for e in entries if e.amount < 0 and e.created_on >= since)
    pending = max(0.0, sum(e.amount for e in entries))

    # Swaps: approved transfers out of this shop = near-expiry stock that did not go to waste.
    moved_units, moved_value, received_units = 0, 0.0, 0
    for sw in db.scalars(select(Swap).where(Swap.status == "approved")):
        if sw.from_shop_id == me.id:
            batch = db.get(Batch, sw.batch_id)
            moved_units += sw.qty
            moved_value += sw.qty * (batch.cost_price if batch else 0.0)
        elif sw.to_shop_id == me.id:
            received_units += sw.qty

    return {
        "simulated": bool(me.is_demo),
        "bulk": {"orders": orders, "spent": round(spent, 2), "saved_estimate": round(max(saved, 0.0), 2),
                 "basis": f"vs a lone kirana paying ~{SOLO_PRICE_RATIO * 100:.0f}% of MRP (assumption)"},
        "pool": {"shops": shops_pooled, "radius_km": NEARBY_RADIUS_KM,
                 "basis": "nearby shops assumed to have joined the pool (demo)"},
        "udhaar": {"recovered_total": round(recovered_all, 2), "recovered_recent": round(recovered_recent, 2),
                   "recent_days": RECENT_DAYS, "pending": round(pending, 2)},
        "swaps": {"units_moved_out": moved_units, "value_moved_out": round(moved_value, 2),
                  "units_received": received_units},
    }
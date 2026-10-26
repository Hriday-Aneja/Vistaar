from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.services.audit_db import append_audit
from app.db.session import get_db
from app.deps import current_user
from app.db.models import Batch, Product, Shop, Swap, User, utcnow
from app.services.swap_engine import suggest

router = APIRouter(prefix="/api/swaps", tags=["swaps"])


class SwapCreateIn(BaseModel):
    batch_id: int
    to_shop_id: int


def _serialize(db: Session, swap: Swap) -> dict:
    return {"id": swap.id, "status": swap.status, "qty": swap.qty, "score": swap.score,
            "breakdown": swap.score_breakdown, "why": swap.why,
            "product": db.get(Product, swap.product_id).name,
            "from_shop_id": swap.from_shop_id, "from_shop": db.get(Shop, swap.from_shop_id).name,
            "to_shop_id": swap.to_shop_id, "to_shop": db.get(Shop, swap.to_shop_id).name,
            "created_at": swap.created_at.isoformat(),
            "decided_at": swap.decided_at.isoformat() if swap.decided_at else None}


@router.get("/suggestions")
def suggestions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return suggest(db, user.shop, date.today())


@router.post("", status_code=201)
def create_swap(body: SwapCreateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = next((p for p in suggest(db, user.shop, date.today())["proposals"]
                  if p["role"] == "send" and p["batch_id"] == body.batch_id and p["to_shop_id"] == body.to_shop_id), None)
    if match is None:
        raise HTTPException(400, "Ye swap ab suggest nahi ho raha, page refresh karo")
    pending = db.scalars(select(Swap).where(Swap.batch_id == body.batch_id, Swap.to_shop_id == body.to_shop_id,
                                            Swap.status == "proposed")).first()
    if pending:
        raise HTTPException(409, "Is swap ka proposal pehle se bheja ja chuka hai")
    swap = Swap(from_shop_id=match["from_shop_id"], to_shop_id=match["to_shop_id"], product_id=match["product_id"],
                batch_id=match["batch_id"], qty=match["qty"], score=match["score"],
                score_breakdown=match["breakdown"], why=match["why"], status="proposed")
    db.add(swap)
    db.commit()
    return _serialize(db, swap)


@router.get("")
def list_swaps(db: Session = Depends(get_db), user: User = Depends(current_user)):
    swaps = db.scalars(select(Swap).where(or_(Swap.from_shop_id == user.shop_id, Swap.to_shop_id == user.shop_id))
                       .order_by(Swap.created_at.desc())).all()
    return [_serialize(db, s) for s in swaps]


@router.post("/{swap_id}/approve")
def approve(swap_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    swap = db.get(Swap, swap_id)
    if swap is None:
        raise HTTPException(404, "Swap nahi mila")
    if swap.to_shop_id != user.shop_id:
        raise HTTPException(403, "Sirf maal lene wali dukaan approve kar sakti hai")
    if swap.status != "proposed":
        raise HTTPException(409, "Is swap par pehle hi faisla ho chuka hai")
    source = db.get(Batch, swap.batch_id)
    if source is None or source.qty_left < swap.qty:
        raise HTTPException(409, "Bhejne wali dukaan ke paas ab itna stock nahi bacha")
    source.qty_left -= swap.qty
    db.add(Batch(shop_id=swap.to_shop_id, product_id=swap.product_id, qty_received=swap.qty, qty_left=swap.qty,
                 cost_price=source.cost_price, sell_price=source.sell_price, received_on=date.today(),
                 expiry_date=source.expiry_date, expiry_source=source.expiry_source, source="swap"))
    swap.status = "approved"
    swap.decided_at = utcnow()
    append_audit(db, "swap", swap.id, {"decision": "approved", "decided_by_user": user.id,
                                       "from_shop_id": swap.from_shop_id, "to_shop_id": swap.to_shop_id,
                                       "product_id": swap.product_id, "batch_id": swap.batch_id, "qty": swap.qty})
    db.commit()
    return _serialize(db, swap)


@router.post("/{swap_id}/reject")
def reject(swap_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    swap = db.get(Swap, swap_id)
    if swap is None:
        raise HTTPException(404, "Swap nahi mila")
    if user.shop_id not in (swap.from_shop_id, swap.to_shop_id):
        raise HTTPException(403, "Ye swap aapki dukaan ka nahi hai")
    if swap.status != "proposed":
        raise HTTPException(409, "Is swap par pehle hi faisla ho chuka hai")
    swap.status = "rejected"
    swap.decided_at = utcnow()
    append_audit(db, "swap", swap.id, {"decision": "rejected", "decided_by_user": user.id,
                                       "from_shop_id": swap.from_shop_id, "to_shop_id": swap.to_shop_id,
                                       "product_id": swap.product_id, "batch_id": swap.batch_id, "qty": swap.qty})
    db.commit()
    return _serialize(db, swap)

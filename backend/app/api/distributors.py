"""Distributors and quotes entered by shop owners.

Real shops only see real distributors and demo shops only demo ones. Owner-entered distributors get
floor_ratio 1.0, so the simulated reverse auction never invents a discount for a real distributor.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Distributor, DistributorQuote, Product, User
from app.db.session import get_db
from app.deps import current_user
from app.schemas import _check_phone
from app.services.audit_db import append_audit

router = APIRouter(prefix="/api/distributors", tags=["distributors"])

MAX_QUOTE_DAYS = 60
MIN_PRICE_SHARE_OF_MRP = 0.3


class DistributorIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, value):
        return _check_phone(value) if value else ""


class QuoteIn(BaseModel):
    product_id: int
    unit_price: float = Field(gt=0, le=100000)
    min_qty: int = Field(ge=1, le=100000)
    delivery_days: int = Field(ge=0, le=30)
    valid_till: date


@router.get("")
def list_distributors(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict]:
    today = date.today()
    shop = user.shop
    out = []
    for d in db.scalars(select(Distributor).where(Distributor.is_demo == shop.is_demo).order_by(Distributor.name)):
        rows = db.execute(select(DistributorQuote, Product).join(Product, DistributorQuote.product_id == Product.id)
                          .where(DistributorQuote.distributor_id == d.id).order_by(Product.name)).all()
        out.append({
            "id": d.id, "name": d.name, "phone": d.phone, "mine": d.added_by_shop_id == shop.id,
            "quotes": [{"id": q.id, "product_id": q.product_id, "product": p.name, "unit_price": q.unit_price,
                        "min_qty": q.min_qty, "delivery_days": q.delivery_days, "valid_till": q.valid_till.isoformat(),
                        "expired": q.valid_till < today} for q, p in rows],
        })
    return out


@router.post("", status_code=201)
def add_distributor(body: DistributorIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    shop = user.shop
    d = Distributor(name=body.name.strip(), phone=body.phone or "", floor_ratio=1.0,
                    is_demo=shop.is_demo, added_by_shop_id=shop.id)
    db.add(d)
    db.commit()
    return {"id": d.id, "name": d.name}


@router.post("/{distributor_id}/quotes", status_code=201)
def add_quote(distributor_id: int, body: QuoteIn, db: Session = Depends(get_db),
              user: User = Depends(current_user)) -> dict:
    shop = user.shop
    d = db.get(Distributor, distributor_id)
    # 404 for both "missing" and "someone else's": do not reveal that another shop's distributor exists
    if d is None or d.is_demo != shop.is_demo or d.added_by_shop_id != shop.id:
        raise HTTPException(404, "Distributor nahi mila")
    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(404, "Product nahi mila")
    if body.unit_price > product.mrp:
        raise HTTPException(400, "Quote MRP se zyada nahi ho sakta")
    if body.unit_price < product.mrp * MIN_PRICE_SHARE_OF_MRP:
        raise HTTPException(400, "Daam bahut kam lag raha hai, dobara check karo")
    today = date.today()
    if not today <= body.valid_till <= today + timedelta(days=MAX_QUOTE_DAYS):
        raise HTTPException(400, f"Quote aaj se {MAX_QUOTE_DAYS} din ke andar tak hi valid ho sakta hai")

    # one live quote per distributor and product: a new quote replaces the old one
    db.execute(delete(DistributorQuote).where(DistributorQuote.distributor_id == d.id,
                                              DistributorQuote.product_id == product.id))
    q = DistributorQuote(distributor_id=d.id, product_id=product.id, unit_price=body.unit_price,
                         min_qty=body.min_qty, delivery_days=body.delivery_days, valid_till=body.valid_till)
    db.add(q)
    db.flush()
    append_audit(db, "distributor_quote", q.id, {"shop_id": shop.id, "distributor_id": d.id, "product_id": product.id,
                                                  "unit_price": body.unit_price, "min_qty": body.min_qty})
    db.commit()
    return {"id": q.id}
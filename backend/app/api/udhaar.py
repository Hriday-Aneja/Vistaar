from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.db.models import Customer, CustomerAlias, KhataEntry, User
from app.schemas import _check_phone
from app.security import phone_hash
from app.services.name_matching import match_customers, suggested_name
from app.services.trust import network_view, shop_stats

router = APIRouter(prefix="/api/udhaar", tags=["udhaar"])


class CustomerIn(BaseModel):
    phone: str
    name: str = Field(min_length=2, max_length=120)
    aliases: list[str] = []

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, value):
        return _check_phone(value)

    @field_validator("aliases")
    @classmethod
    def aliases_ok(cls, value):
        cleaned = [a.strip()[:40] for a in value if a.strip()]
        if len(cleaned) > 5:
            raise ValueError("Zyada se zyada 5 nickname")
        return cleaned


class AliasIn(BaseModel):
    alias: str = Field(min_length=2, max_length=40)


class EntryIn(BaseModel):
    customer_id: int
    kind: str = Field(pattern="^(credit|payment)$")
    amount: float = Field(gt=0, le=1000000)
    note: Optional[str] = Field(default=None, max_length=200)


def _own_customer(db: Session, user: User, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.shop_id != user.shop_id:
        raise HTTPException(404, "Customer nahi mila")
    return customer


def _card(db: Session, customer: Customer, today: date) -> dict:
    stats = shop_stats(db, customer.shop_id, customer.id, today)
    return {"id": customer.id, "display_name": customer.display_name, "phone_masked": "XXXXXX" + customer.phone[-4:],
            "aliases": [a.alias for a in customer.aliases], "pending": stats["pending"],
            "last_visit": customer.last_visit.isoformat() if customer.last_visit else None}


@router.get("/customers")
def list_customers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    customers = db.scalars(select(Customer).where(Customer.shop_id == user.shop_id).order_by(Customer.display_name)).all()
    return [_card(db, c, today) for c in customers]


@router.get("/resolve")
def resolve(q: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    customers = db.scalars(select(Customer).where(Customer.shop_id == user.shop_id)).all()
    matches = match_customers(q, customers)
    cards = [{**_card(db, m["customer"], today), "match_reason": m["reason"]} for m in matches]
    if not cards:
        return {"status": "none", "suggested_name": suggested_name(q), "matches": []}
    if len(cards) == 1:
        return {"status": "resolved", "matches": cards}
    first = suggested_name(q).split(" ")[0] or "customer"
    return {"status": "ambiguous", "question": f"Kaun sa {first}?", "matches": cards}


@router.post("/customers", status_code=201)
def create_customer(body: CustomerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    existing = db.scalars(select(Customer).where(Customer.shop_id == user.shop_id, Customer.phone == body.phone)).first()
    if existing:
        raise HTTPException(409, f"Ye number pehle se hai: {existing.display_name}")
    customer = Customer(shop_id=user.shop_id, phone=body.phone, phone_hash=phone_hash(body.phone),
                        display_name=body.name.strip(), last_visit=date.today())
    customer.aliases = [CustomerAlias(alias=a) for a in body.aliases]
    db.add(customer)
    db.commit()
    return _card(db, customer, date.today())


@router.post("/customers/{customer_id}/aliases", status_code=201)
def add_alias(customer_id: int, body: AliasIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = _own_customer(db, user, customer_id)
    db.add(CustomerAlias(customer_id=customer.id, alias=body.alias.strip()))
    db.commit()
    return _card(db, db.get(Customer, customer.id), date.today())


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    customer = _own_customer(db, user, customer_id)
    recent = db.scalars(select(KhataEntry).where(KhataEntry.customer_id == customer.id)
                        .order_by(KhataEntry.created_on.desc(), KhataEntry.id.desc()).limit(5)).all()
    return {"customer": _card(db, customer, today), "local": shop_stats(db, user.shop_id, customer.id, today),
            "recent": [{"amount": e.amount, "note": e.note, "date": e.created_on.isoformat()} for e in recent],
            "network": network_view(db, user.shop, customer, today)}


@router.post("/entries", status_code=201)
def add_entry(body: EntryIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    customer = _own_customer(db, user, body.customer_id)
    pending = shop_stats(db, user.shop_id, customer.id, today)["pending"]
    if body.kind == "payment" and body.amount > pending:
        raise HTTPException(400, f"Sirf Rs {pending:.0f} baaki hai")
    amount = body.amount if body.kind == "credit" else -body.amount
    db.add(KhataEntry(shop_id=user.shop_id, customer_id=customer.id, amount=amount,
                      note=(body.note or ("udhaar" if amount > 0 else "payment")), created_on=today))
    customer.last_visit = today
    db.commit()
    return _card(db, customer, today)

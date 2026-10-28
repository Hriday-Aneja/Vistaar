from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.db.models import Batch, Product, Sale, User
from app.schemas import BatchIn, SaleIn
from app.services.backdate import check_backdate, noon_of
from app.services.catalog import CATEGORY_SHELF_DAYS, get_or_create_product
from app.services.expiry import assess, effective_expiry
from app.services.inventory import daily_rate

router = APIRouter(prefix="/api", tags=["stock"])


@router.get("/categories")
def categories():
    return [{"name": name, "default_shelf_days": days} for name, days in CATEGORY_SHELF_DAYS.items()]


@router.get("/products")
def search_products(q: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Product).order_by(Product.name).limit(20)
    if q.strip():
        stmt = select(Product).where(Product.name.ilike(f"%{q.strip()}%")).order_by(Product.name).limit(20)
    return [{"id": p.id, "name": p.name, "category": p.category, "mrp": p.mrp} for p in db.scalars(stmt)]


@router.post("/stock/batches", status_code=201)
def add_batch(body: BatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    product = get_or_create_product(db, body.product_id, body.product_name, body.category, body.mrp or body.sell_price)
    received = body.received_on or date.today()
    expiry, source = effective_expiry(body.expiry_date, "entered", received, product.default_shelf_days)
    batch = Batch(shop_id=user.shop_id, product_id=product.id, qty_received=body.qty, qty_left=body.qty,
                  cost_price=body.cost_price, sell_price=body.sell_price, received_on=received,
                  expiry_date=expiry, expiry_source=source, source="manual")
    db.add(batch)
    db.commit()
    return {"batch_id": batch.id, "product": product.name, "expiry_date": expiry.isoformat(),
            "expiry_source": source}


@router.get("/stock")
def list_stock(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    rows = db.execute(
        select(Batch, Product).join(Product, Batch.product_id == Product.id)
        .where(Batch.shop_id == user.shop_id, Batch.qty_left > 0)
        .order_by(Batch.expiry_date)
    ).all()
    rates, out = {}, []
    for batch, product in rows:
        if product.id not in rates:
            rates[product.id] = daily_rate(db, user.shop_id, product.id, today)
        risk = assess(batch.qty_left, rates[product.id], today, batch.expiry_date, batch.received_on)
        out.append({"batch_id": batch.id, "product_id": product.id, "product": product.name,
                    "category": product.category, "qty_left": batch.qty_left, "sell_price": batch.sell_price,
                    "received_on": batch.received_on.isoformat(),
                    "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                    "expiry_source": batch.expiry_source, "daily_rate": rates[product.id], "risk": risk})
    return out


@router.post("/sales", status_code=201)
def record_sale(body: SaleIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    when = {}  # empty = the column default, i.e. now
    if body.sold_on is not None:
        try:
            check_backdate(body.sold_on, date.today())
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        when = {"sold_at": noon_of(body.sold_on)}
    batches = db.scalars(
        select(Batch).where(Batch.shop_id == user.shop_id, Batch.product_id == body.product_id, Batch.qty_left > 0)
        .order_by(Batch.expiry_date.is_(None), Batch.expiry_date, Batch.received_on)
    ).all()
    available = sum(b.qty_left for b in batches)
    if available < body.qty:
        raise HTTPException(400, f"Sirf {available} bache hain")
    remaining, sale_ids = body.qty, []
    for batch in batches:
        if remaining == 0:
            break
        take = min(batch.qty_left, remaining)
        price = body.unit_price or batch.sell_price
        batch.qty_left -= take
        sale = Sale(shop_id=user.shop_id, product_id=body.product_id, batch_id=batch.id, qty=take,
                    amount=round(take * price, 2), is_simulated=0, **when)
        db.add(sale)
        db.flush()
        sale_ids.append(sale.id)
        remaining -= take
    db.commit()
    return {"sale_ids": sale_ids, "qty": body.qty}
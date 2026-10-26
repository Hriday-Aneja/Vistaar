from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Product

CATEGORY_SHELF_DAYS = {
    "Biscuits": 120,
    "Snacks": 120,
    "Frozen": 180,
    "Beverages": 180,
    "Dairy": 3,
    "Bakery": 4,
    "Fruits & Vegetables": 5,
    "Staples": 180,
    "Instant food": 270,
    "Household": 730,
    "Other": 180,
}


def shelf_days_for(category: str) -> int:
    return CATEGORY_SHELF_DAYS.get(category, CATEGORY_SHELF_DAYS["Other"])


def get_or_create_product(db: Session, product_id: Optional[int], name: Optional[str],
                          category: Optional[str], mrp: Optional[float]) -> Product:
    if product_id is not None:
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(404, "Product nahi mila")
        return product
    existing = db.scalars(select(Product).where(func.lower(Product.name) == name.strip().lower())).first()
    if existing:
        return existing
    product = Product(name=name.strip(), category=category, unit="pack",
                      default_shelf_days=shelf_days_for(category), mrp=mrp)
    db.add(product)
    db.flush()
    return product

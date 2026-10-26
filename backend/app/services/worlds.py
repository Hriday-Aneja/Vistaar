from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Shop


def same_world(db: Session, shop: Shop) -> list[Shop]:
    """Demo shops only ever interact with demo shops; real shops only with real shops."""
    return [s for s in db.scalars(select(Shop)) if s.is_demo == shop.is_demo]

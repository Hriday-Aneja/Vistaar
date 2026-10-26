from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.tuning import NEARBY_RADIUS_KM
from app.db.session import get_db
from app.deps import current_user
from app.db.models import User
from app.services.geo import nearby
from app.services.worlds import same_world

router = APIRouter(prefix="/api/shops", tags=["shops"])


@router.get("")
def map_shops(db: Session = Depends(get_db), user: User = Depends(current_user)):
    me = user.shop
    return {
        "radius_km": NEARBY_RADIUS_KM,
        "me": {"id": me.id, "name": me.name, "area": me.area, "lat": me.lat, "lng": me.lng},
        "nearby": [{"id": s.id, "name": s.name, "area": s.area, "lat": s.lat, "lng": s.lng, "distance_km": d}
                   for s, d in nearby(me, same_world(db, me), NEARBY_RADIUS_KM)],
    }

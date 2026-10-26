from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.db.models import User
from app.services.pulse import pulse_for
from app.services.sales_drop import sales_drop_for

router = APIRouter(prefix="/api/pulse", tags=["pulse"])


@router.get("")
def pulse(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return pulse_for(db, user.shop, date.today())


@router.get("/drops")
def drops(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return sales_drop_for(db, user.shop, date.today())
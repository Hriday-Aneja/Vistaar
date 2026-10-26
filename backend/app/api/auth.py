import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tuning import SESSION_HOURS
from app.db.session import get_db
from app.deps import current_user
from app.db.models import AuthToken, Shop, User, utcnow
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_token(db: Session, user: User) -> TokenOut:
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token=token, user_id=user.id, expires_at=utcnow() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return TokenOut(token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalars(select(User).where(User.phone == body.phone)).first():
        raise HTTPException(409, "Is number se account pehle se hai, login karo")
    shop = Shop(name=body.shop_name.strip(), owner_name=body.name.strip(), area=body.area.strip(),
                lat=body.lat, lng=body.lng, upi_vpa=body.upi_vpa or "", is_demo=False)
    db.add(shop)
    db.flush()
    user = User(phone=body.phone, name=body.name.strip(), password_hash=hash_password(body.password), shop_id=shop.id)
    db.add(user)
    db.flush()
    return _issue_token(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.phone == body.phone)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Number ya password galat hai")
    return _issue_token(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()

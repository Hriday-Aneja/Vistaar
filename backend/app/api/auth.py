import secrets
from datetime import timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tuning
from app.tuning import SESSION_HOURS
from app.db.session import get_db
from app.deps import current_user
from app.db.models import AuthToken, Shop, User, utcnow
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import hash_password, normalize_phone, verify_password
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Wrong passwords are counted per phone number (also for numbers with no account, so the answer reveals nothing)
# and, with a much higher limit, per client IP.
_login_by_phone = SlidingWindowLimiter(tuning.LOGIN_MAX_FAILURES, tuning.LOGIN_WINDOW_S)
_login_by_ip = SlidingWindowLimiter(tuning.LOGIN_MAX_FAILURES_PER_IP, tuning.LOGIN_WINDOW_S)
_register_by_ip = SlidingWindowLimiter(tuning.REGISTER_MAX_PER_IP, tuning.REGISTER_WINDOW_S)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many(seconds: int) -> HTTPException:
    return HTTPException(429, f"Bahut zyada koshish ho gayi. {ceil(seconds / 60)} minute baad dobara try karo",
                         headers={"Retry-After": str(seconds)})


def _issue_token(db: Session, user: User) -> TokenOut:
    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token=token, user_id=user.id, expires_at=utcnow() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return TokenOut(token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    wait = _register_by_ip.retry_after(ip)
    if wait:
        raise _too_many(wait)
    _register_by_ip.add(ip)
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
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    phone, ip = normalize_phone(body.phone), _client_ip(request)
    wait = max(_login_by_phone.retry_after(phone), _login_by_ip.retry_after(ip))
    if wait:
        raise _too_many(wait)
    user = db.scalars(select(User).where(User.phone == body.phone)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        _login_by_phone.add(phone)
        _login_by_ip.add(ip)
        raise HTTPException(401, "Number ya password galat hai")
    _login_by_phone.clear(phone)
    return _issue_token(db, user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AuthToken, User, utcnow
from app.db.session import get_db


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Pehle login karo")
    row = db.get(AuthToken, token)
    if row is None or row.expires_at < utcnow():
        raise HTTPException(401, "Session khatam ho gaya, dobara login karo")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(401, "Account nahi mila")
    return user

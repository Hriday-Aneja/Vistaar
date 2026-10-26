from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.audit_db import verify_chain

router = APIRouter()


@router.get("/health")
@router.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok", "service": "vistaar-api", "audit_chain": verify_chain(db)}

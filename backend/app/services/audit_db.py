import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog

GENESIS = "0" * 64


def _digest(seq: int, kind: str, ref_id: int, payload: dict, prev_hash: str, created_at: datetime) -> str:
    body = json.dumps(
        {"seq": seq, "kind": kind, "ref_id": ref_id, "payload": payload,
         "prev_hash": prev_hash, "created_at": created_at.isoformat()},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def append_audit(db: Session, kind: str, ref_id: int, payload: dict) -> AuditLog:
    last = db.scalars(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).first()
    seq = 1 if last is None else last.seq + 1
    prev_hash = GENESIS if last is None else last.hash
    created_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    entry = AuditLog(
        seq=seq, kind=kind, ref_id=ref_id, payload=payload, prev_hash=prev_hash,
        hash=_digest(seq, kind, ref_id, payload, prev_hash, created_at), created_at=created_at,
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    rows = db.scalars(select(AuditLog).order_by(AuditLog.seq)).all()
    for row in rows:
        expected = _digest(row.seq, row.kind, row.ref_id, row.payload, prev, row.created_at)
        if row.prev_hash != prev or row.hash != expected:
            return {"ok": False, "broken_at": row.seq, "length": len(rows)}
        prev = row.hash
    return {"ok": True, "broken_at": None, "length": len(rows)}

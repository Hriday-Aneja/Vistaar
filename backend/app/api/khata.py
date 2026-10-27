"""Khata reminders: drafted automatically, sent only when the merchant presses send."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Customer, KhataReminder, User
from app.db.session import get_db
from app.deps import current_user
from app.services.audit_db import append_audit
from app.services.llm import get_router
from app.services.reminders import ReminderJob, draft_message, draft_messages_llm
from app.services.trust import shop_stats
from app.services.upi import build_upi_link

router = APIRouter(prefix="/api/khata", tags=["khata"])

MIN_OVERDUE_DAYS = 7


class SendIn(BaseModel):
    customer_id: int
    message: str = Field(min_length=5, max_length=600)


def _draft(user: User, customer: Customer, stats: dict, worded: tuple[str, str] | None = None) -> dict:
    """worded: (provider, message) from the LLM, or None for the fixed template."""
    link = build_upi_link(user.shop.upi_vpa or "shop@upi", user.shop.name, stats["pending"], "Khata payment")
    template = draft_message(user.shop.name, customer.display_name, stats["pending"], stats["overdue_days"], link)
    return {"customer_id": customer.id, "display_name": customer.display_name, "pending": stats["pending"],
            "overdue_days": stats["overdue_days"], "upi_link": link,
            "message": worded[1] if worded else template, "message_source": worded[0] if worded else "template"}


@router.get("/drafts")
def drafts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    due = []
    for c in db.scalars(select(Customer).where(Customer.shop_id == user.shop_id)):
        stats = shop_stats(db, user.shop_id, c.id, today)
        if stats["pending"] > 0 and stats["overdue_days"] >= MIN_OVERDUE_DAYS:
            due.append((c, stats))
    due.sort(key=lambda cs: cs[1]["pending"], reverse=True)
    # The LLM only words the message (own customers' first names and amounts, never phone numbers or links).
    # The template is the fallback. Either way this is a draft: nothing is sent until the merchant approves.
    jobs = [ReminderJob(user.shop_id, c.id, user.shop.name, c.display_name, stats["pending"], stats["overdue_days"],
                        build_upi_link(user.shop.upi_vpa or "shop@upi", user.shop.name, stats["pending"], "Khata payment"))
            for c, stats in due]
    worded = draft_messages_llm(get_router(), jobs)
    return [_draft(user, c, stats, worded.get(c.id)) for c, stats in due]


@router.post("/send", status_code=201)
def send(body: SendIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = db.get(Customer, body.customer_id)
    if customer is None or customer.shop_id != user.shop_id:
        raise HTTPException(404, "Customer nahi mila")
    stats = shop_stats(db, user.shop_id, customer.id, date.today())
    if stats["pending"] <= 0:
        raise HTTPException(400, "Is customer ka kuch baaki nahi hai")
    link = build_upi_link(user.shop.upi_vpa or "shop@upi", user.shop.name, stats["pending"], "Khata payment")
    row = KhataReminder(shop_id=user.shop_id, customer_id=customer.id, message=body.message,
                        upi_link=link, channel="mock")  # TODO: WhatsApp Business API when enabled
    db.add(row)
    db.flush()
    append_audit(db, "khata_reminder", row.id, {"customer_id": customer.id, "shop_id": user.shop_id,
                                                "pending": stats["pending"], "approved_by_user": user.id})
    db.commit()
    return {"id": row.id, "channel": row.channel, "status": "sent (simulated)"}

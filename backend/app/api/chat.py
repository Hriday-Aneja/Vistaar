"""Chat intent: which feature does the merchant's message ask for? The page then calls that feature's own API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import tuning
from app.db.models import User
from app.deps import current_user
from app.services.chat_intent import detect_intent
from app.services.llm import get_router
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/api/chat", tags=["chat"])
_limiter = SlidingWindowLimiter(limit=tuning.LLM_INTENT_PER_MIN, window_s=60)


class IntentIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.post("/intent")
def intent(body: IntentIn, user: User = Depends(current_user)) -> dict:
    key = f"user:{user.id}"
    use_llm = _limiter.retry_after(key) == 0  # over the limit: keyword routing answers, the chat keeps working
    if use_llm:
        _limiter.add(key)
    return detect_intent(get_router(), body.text.strip(), use_llm=use_llm)

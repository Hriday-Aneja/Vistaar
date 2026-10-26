import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.models import AuthToken, Distributor, PlanThread, User, utcnow
from app.db.session import SessionLocal

router = APIRouter(tags=["stream"])

REPLAY_DELAY_S = 0.7  # pause between bids so the live panel visibly fills in


@router.websocket("/ws/negotiation/{thread_id}")
async def negotiation_stream(ws: WebSocket, thread_id: str, token: str = "") -> None:
    """Replays the auction events of a saved plan, one bid at a time. Only the shop that made the plan may listen."""
    with SessionLocal() as db:
        row = db.get(AuthToken, token) if token else None
        user = db.get(User, row.user_id) if row is not None and row.expires_at >= utcnow() else None
        plan = db.get(PlanThread, thread_id)
        allowed = user is not None and plan is not None and plan.shop_id == user.shop_id
        events = list(plan.state["auction_log"]) if allowed else []
        names = {d.id: d.name for d in db.scalars(select(Distributor))}

    await ws.accept()
    if not allowed:
        await ws.close(code=4401)
        return

    try:
        await ws.send_json({"event": "connected", "total": len(events)})
        for e in events:
            await asyncio.sleep(REPLAY_DELAY_S)
            did = e["distributor_id"]
            await ws.send_json({
                "event": "bid", "round": e["round"], "distributor_id": did,
                "distributor": names.get(int(did), f"#{did}"), "sku": e.get("product"), "price": e["price"],
            })
        await ws.send_json({"event": "done", "count": len(events)})
        await ws.close()
    except WebSocketDisconnect:
        return
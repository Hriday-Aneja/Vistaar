"""Live alerts: WebSocket /ws/alerts forwards the events published to the caller's own shop channel.

Same token check as api/stream.py (?token=, close code 4401 when it is missing, bad or expired). The channel comes
from the token's own shop, so a user cannot listen to another shop's alerts: there is no shop id to pass.
If Redis is not reachable the socket sends {"event": "unavailable"} and closes; the Pulse page then polls.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.db.models import AuthToken, User, utcnow
from app.db.session import SessionLocal
from app.services import alert_bus

log = logging.getLogger(__name__)
router = APIRouter(tags=["alerts"])

HEARTBEAT_S = 25  # keeps idle proxies from closing the socket


def _shop_for_token(token: str) -> int | None:
    with SessionLocal() as db:
        row = db.get(AuthToken, token) if token else None
        user = db.get(User, row.user_id) if row is not None and row.expires_at >= utcnow() else None
        return user.shop_id if user is not None else None


async def _forward(ws: WebSocket, messages) -> None:
    async def pump() -> None:
        async for raw in messages:
            try:
                await ws.send_json(json.loads(raw))
            except ValueError:
                continue  # not JSON: ignore it

    async def watch_client() -> None:
        while True:
            await ws.receive_text()  # raises WebSocketDisconnect when the client leaves

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            await ws.send_json({"event": "ping"})

    tasks = [asyncio.create_task(c()) for c in (pump, watch_client, heartbeat)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            t.result()
    finally:
        for t in tasks:
            t.cancel()


@router.websocket("/ws/alerts")
async def alerts_stream(ws: WebSocket, token: str = "") -> None:
    shop_id = await run_in_threadpool(_shop_for_token, token)
    await ws.accept()
    if shop_id is None:
        await ws.close(code=4401)
        return
    try:
        async with alert_bus.get_bus().subscribe(alert_bus.channel_for(shop_id)) as messages:
            await ws.send_json({"event": "connected"})  # sent after subscribing, so nothing published later is missed
            await _forward(ws, messages)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001 - Redis down or dropped: tell the page to poll
        log.info("alerts stream for shop %s unavailable: %s", shop_id, exc)
        try:
            await ws.send_json({"event": "unavailable"})
            await ws.close(code=1011)
        except Exception:  # noqa: BLE001, S110
            pass

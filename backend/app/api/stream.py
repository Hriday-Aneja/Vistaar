from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["stream"])


@router.websocket("/ws/negotiation")
async def negotiation_stream(ws: WebSocket) -> None:
    """TODO: subscribe to a Redis Pub/Sub channel and forward live negotiation events."""
    await ws.accept()
    await ws.send_json({"event": "connected"})
    await ws.close()

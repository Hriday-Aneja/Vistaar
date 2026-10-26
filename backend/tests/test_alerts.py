"""Live alerts over Pub/Sub: events from the Celery monitors, the /ws/alerts socket, and every Redis-down path.

Nothing here talks to a real Redis: an in-memory bus stands in, and the "Redis is down" cases point at a closed
local port.
"""
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("langgraph")

from sqlalchemy import select

from app.services import alert_bus


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app import seed
    from app.main import app

    seed.build()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bus():
    fake = alert_bus.InMemoryBus()
    alert_bus.set_bus(fake)
    yield fake
    alert_bus.set_bus(None)


def _login(client, phone="9000000001"):
    r = client.post("/api/auth/login", json={"phone": phone, "password": "vistaar123"})
    assert r.status_code == 200
    return r.json()["token"]


def _shop_id(phone):
    from app.db.models import User
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        return db.scalar(select(User.shop_id).where(User.phone == phone))


def _events(bus, shop_id):
    return [json.loads(m) for ch, m in bus.published if ch == f"alerts:{shop_id}"]


def test_channel_name():
    assert alert_bus.channel_for(7) == "alerts:7"


def test_publish_goes_to_the_shop_channel_as_json(bus):
    assert alert_bus.publish_alert(3, {"event": "alert", "kind": "pulse", "n": 1}) is True
    assert bus.published == [("alerts:3", '{"event": "alert", "kind": "pulse", "n": 1}')]


def test_publish_is_silent_when_the_bus_is_off_or_redis_is_down(monkeypatch):
    alert_bus.set_bus(alert_bus.NullBus())
    assert alert_bus.publish_alert(1, {"x": 1}) is False  # switched off: quiet no-op

    alert_bus.set_bus(alert_bus.RedisBus("redis://127.0.0.1:1/0"))  # nothing listens on port 1
    assert alert_bus.publish_alert(1, {"x": 1}) is False  # connection refused, but no exception
    alert_bus.set_bus(None)


def test_after_a_failure_redis_is_skipped_for_a_while(monkeypatch):
    attempts = []

    class Broken:
        def publish(self, channel, message):
            attempts.append(channel)
            raise ConnectionError("down")

    alert_bus.set_bus(Broken())
    assert alert_bus.publish_alert(1, {}) is False and alert_bus.publish_alert(1, {}) is False
    assert attempts == ["alerts:1"]  # the second call did not even try
    monkeypatch.setattr(alert_bus, "_down_until", 0.0)  # the pause is over
    alert_bus.publish_alert(1, {})
    assert len(attempts) == 2
    alert_bus.set_bus(None)


def test_monitor_pulse_saves_and_publishes_once_per_alert(client, bus):
    from app.db.models import PulseAlert
    from app.db.session import SessionLocal
    from app.workers.tasks import monitor_pulse

    found = monitor_pulse()
    assert found >= 1
    shop = _shop_id("9000000003")  # one of the shops in the seeded ice-cream spike
    mine = [e for e in _events(bus, shop) if e["kind"] == "pulse"]
    assert any(e["product"] == "Ice Cream Cone" for e in mine)
    event = next(e for e in mine if e["product"] == "Ice Cream Cone")
    assert event["event"] == "alert" and event["shop_id"] == shop and event["id"] and event["action"] and event["why"]
    with SessionLocal() as db:
        rows = db.scalars(select(PulseAlert).where(PulseAlert.shop_id == shop)).all()
        assert {r.id for r in rows} >= {e["id"] for e in mine} and all(r.status == "open" for r in rows)
        saved = db.scalar(select(PulseAlert.id).order_by(PulseAlert.id.desc()))

    before = len(bus.published)
    assert monitor_pulse() == found  # still counts every alert...
    assert len(bus.published) == before  # ...but an open alert from the last 24 h is not published twice
    with SessionLocal() as db:
        assert db.scalar(select(PulseAlert.id).order_by(PulseAlert.id.desc())) == saved


def test_events_only_go_to_the_shops_own_channel(client, bus):
    from app.workers.tasks import monitor_pulse

    monitor_pulse()
    for channel, message in bus.published:
        assert json.loads(message)["shop_id"] == int(channel.split(":")[1])
    assert not any("phone" in m for _, m in bus.published)  # nothing personal or about other shops


def test_monitor_sales_publishes_the_drop_for_the_dropping_shop(client, bus):
    from app.workers.tasks import monitor_sales

    assert monitor_sales() >= 1
    drops = _events(bus, _shop_id("9000000006"))
    assert [e["kind"] for e in drops] == ["sales_drop"]
    assert drops[0]["drop"]["drop_pct"] >= 40 and drops[0]["id"] is None
    assert _events(bus, _shop_id("9000000001")) == []  # a healthy shop gets nothing


def test_task_still_finishes_when_redis_is_down(client):
    from app.workers.tasks import monitor_pulse, monitor_sales

    alert_bus.set_bus(alert_bus.RedisBus("redis://127.0.0.1:1/0"))
    try:
        assert monitor_pulse() >= 0 and monitor_sales() >= 1
    finally:
        alert_bus.set_bus(None)


def test_ws_alerts_delivers_my_events_and_nothing_else(client, bus):
    token = _login(client)
    mine, other = _shop_id("9000000001"), _shop_id("9000000002")
    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        assert ws.receive_json() == {"event": "connected"}
        alert_bus.publish_alert(other, {"event": "alert", "kind": "pulse", "id": 111, "shop_id": other})
        alert_bus.publish_alert(mine, {"event": "alert", "kind": "sales_drop", "id": None, "shop_id": mine})
        got = ws.receive_json()  # the other shop's event was never delivered, so this is the first one
        assert got["kind"] == "sales_drop" and got["shop_id"] == mine


def test_ws_alerts_rejects_a_bad_or_missing_token(client, bus):
    from starlette.websockets import WebSocketDisconnect

    for url in ("/ws/alerts?token=bad", "/ws/alerts"):
        with client.websocket_connect(url) as ws:
            with pytest.raises(WebSocketDisconnect) as stop:
                ws.receive_json()
            assert stop.value.code == 4401


def test_ws_alerts_says_unavailable_when_redis_is_down(client):
    alert_bus.set_bus(alert_bus.RedisBus("redis://127.0.0.1:1/0"))
    try:
        with client.websocket_connect(f"/ws/alerts?token={_login(client)}") as ws:
            assert ws.receive_json() == {"event": "unavailable"}
    finally:
        alert_bus.set_bus(None)


def test_ws_alerts_says_unavailable_when_alerts_are_switched_off(client):
    alert_bus.set_bus(alert_bus.NullBus())
    try:
        with client.websocket_connect(f"/ws/alerts?token={_login(client)}") as ws:
            assert ws.receive_json() == {"event": "unavailable"}
    finally:
        alert_bus.set_bus(None)


def test_negotiation_stream_and_alert_apis_are_untouched(client):
    h = {"Authorization": f"Bearer {_login(client)}"}
    assert client.get("/api/pulse", headers=h).status_code == 200
    assert set(client.get("/api/pulse/drops", headers=h).json()) >= {"drop", "through", "days_of_data", "message"}

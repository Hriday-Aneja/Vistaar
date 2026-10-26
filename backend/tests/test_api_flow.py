"""End-to-end API tests on a seeded SQLite DB. Skipped if the web stack isn't installed."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("langgraph")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app import seed
    from app.main import app

    seed.build()
    with TestClient(app) as c:
        yield c


def _login(client, phone="9000000001"):
    r = client.post("/api/auth/login", json={"phone": phone, "password": "vistaar123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health_and_auth(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/stock").status_code == 401
    assert client.get("/api/stock", headers=_login(client)).status_code == 200


def test_swap_engine_finds_the_biscuit_swap(client):
    r = client.get("/api/swaps/suggestions", headers=_login(client)).json()
    assert any(p["product"] == "Marie Gold Biscuits" and p["role"] == "send" for p in r["proposals"])


def test_udhaar_network_and_cold_start(client):
    h = _login(client)
    match = client.get("/api/udhaar/resolve", params={"q": "Rahul bhai ko udhaar du?"}, headers=h).json()
    cid = match["matches"][0]["id"]
    detail = client.get(f"/api/udhaar/customers/{cid}", headers=h).json()
    assert detail["network"]["status"] == "ok" and detail["network"]["level"] in ("Low", "Medium", "High")
    mohan = client.get("/api/udhaar/resolve", params={"q": "Mohan"}, headers=h).json()["matches"][0]["id"]
    assert client.get(f"/api/udhaar/customers/{mohan}", headers=h).json()["network"]["status"] == "not_enough_data"


def test_pulse_detects_ice_cream_spike(client):
    alerts = client.get("/api/pulse", headers=_login(client, "9000000003")).json()["alerts"]
    assert any(a["product"] == "Ice Cream Cone" for a in alerts)


def test_price_radar_flags_inflated_atta(client):
    rows = client.get("/api/prices/radar", headers=_login(client)).json()
    atta = next(r for r in rows if r["product"] == "Atta 5kg")
    assert any(q["flag"] and q["flag"]["level"] == "inflated" for q in atta["quotes"])


def test_bulk_plan_requires_approval_then_orders(client):
    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    assert plan["status"] == "awaiting_approval" and plan["cohort_size"] >= 5 and plan["lines"]
    done = client.post(f"/api/orders/{plan['thread_id']}/approve", headers=h).json()
    assert done["status"] == "ordered" and done["order_ids"]
    assert client.get("/health").json()["audit_chain"]["ok"] is True


def test_negotiation_stream_replays_auction(client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr("app.api.stream.REPLAY_DELAY_S", 0)
    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    token = h["Authorization"].split(" ")[1]
    bids = []
    with client.websocket_connect(f"/ws/negotiation/{plan['thread_id']}?token={token}") as ws:
        while True:
            msg = ws.receive_json()
            if msg["event"] == "done":
                break
            if msg["event"] == "bid":
                bids.append(msg)
    assert len(bids) == len(plan["auction_log"])
    with client.websocket_connect(f"/ws/negotiation/{plan['thread_id']}?token=bad") as ws:
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_impact_numbers_and_labels(client):
    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    client.post(f"/api/orders/{plan['thread_id']}/approve", headers=h)
    r = client.get("/api/impact", headers=h).json()
    assert r["simulated"] is True
    assert r["bulk"]["orders"] >= 1 and "assumption" in r["bulk"]["basis"]
    assert r["pool"]["shops"] >= 5
    assert r["udhaar"]["recovered_total"] >= 0
    assert client.get("/api/impact").status_code == 401


def test_bulk_plan_explains_each_quantity(client):
    plan = client.post("/api/orders/plan", headers=_login(client)).json()
    mine = [ln for ln in plan["lines"] if ln["my_qty"] > 0]
    assert mine and all(ln["reason"] and "aur chahiye" in ln["reason"] for ln in mine)
    assert "not ML" in plan["forecast_method"]


def test_sales_drop_alert_for_the_dropping_shop(client):
    r = client.get("/api/pulse/drops", headers=_login(client, "9000000006")).json()
    assert r["drop"] is not None and r["drop"]["drop_pct"] >= 40
    assert "through" in client.get("/api/pulse/drops", headers=_login(client)).json()


def test_pending_plan_survives_a_restart(client, monkeypatch):
    from app.agents.graph import build_graph
    from app.api import orders

    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    monkeypatch.setattr(orders, "_graph", build_graph())  # fresh in-memory state, like a server restart
    done = client.post(f"/api/orders/{plan['thread_id']}/approve", headers=h).json()
    assert done["status"] == "ordered" and done["order_ids"]


def test_approve_twice_returns_same_orders_and_only_owner_can_approve(client):
    h = _login(client)
    plan = client.post("/api/orders/plan", headers=h).json()
    url = f"/api/orders/{plan['thread_id']}/approve"
    assert client.post(url, headers=_login(client, "9000000002")).status_code == 404
    first = client.post(url, headers=h).json()
    again = client.post(url, headers=h).json()
    assert first["order_ids"] == again["order_ids"] and again["status"] == "ordered"
    assert client.post("/api/orders/unknown-thread/approve", headers=h).status_code == 404
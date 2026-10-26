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

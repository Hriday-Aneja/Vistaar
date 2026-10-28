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


def _register_real(client, phone):
    r = client.post("/api/auth/register", json={"phone": phone, "name": "Asha Devi", "password": "secret123",
                    "shop_name": "Asha Kirana", "area": "Rohini", "lat": 28.7, "lng": 77.1})
    assert r.status_code == 201
    return {"Authorization": "Bearer " + r.json()["token"]}


def _quote(product, **over):
    from datetime import date, timedelta
    body = {"product_id": product["id"], "unit_price": round(product["mrp"] * 0.8, 2), "min_qty": 20,
            "delivery_days": 2, "valid_till": (date.today() + timedelta(days=7)).isoformat()}
    return {**body, **over}


def test_real_shop_world_is_separate_from_demo(client):
    real = _register_real(client, "9111111111")
    assert client.get("/api/distributors", headers=real).json() == []
    assert client.get("/api/prices/radar", headers=real).json() == []
    plan = client.post("/api/orders/plan", headers=real).json()
    assert plan["lines"] == [] and plan["cohort_size"] == 1

    d = client.post("/api/distributors", json={"name": "Real Wholesale"}, headers=real).json()
    atta = client.get("/api/products", params={"q": "Atta"}, headers=real).json()[0]
    assert client.post(f"/api/distributors/{d['id']}/quotes", json=_quote(atta), headers=real).status_code == 201
    radar = client.get("/api/prices/radar", headers=real).json()
    assert any(q["distributor"] == "Real Wholesale" and q["after_auction"] == q["unit_price"]
               for row in radar for q in row["quotes"])

    demo = _login(client)
    assert "Real Wholesale" not in [x["name"] for x in client.get("/api/distributors", headers=demo).json()]
    assert not any(q["distributor"] == "Real Wholesale"
                   for row in client.get("/api/prices/radar", headers=demo).json() for q in row["quotes"])


def test_quote_rules_and_ownership(client):
    owner = _register_real(client, "9122222222")
    other = _register_real(client, "9133333333")
    d = client.post("/api/distributors", json={"name": "Owner Traders", "phone": "9876543210"}, headers=owner).json()
    atta = client.get("/api/products", params={"q": "Atta"}, headers=owner).json()[0]
    url = f"/api/distributors/{d['id']}/quotes"
    assert client.post(url, json=_quote(atta, unit_price=atta["mrp"] + 1), headers=owner).status_code == 400
    assert client.post(url, json=_quote(atta, unit_price=0.5), headers=owner).status_code in (400, 422)
    assert client.post(url, json=_quote(atta, valid_till="2000-01-01"), headers=owner).status_code == 400
    assert client.post(url, json=_quote(atta), headers=other).status_code == 404
    assert client.post(url, json=_quote(atta), headers=_login(client)).status_code == 404
    assert client.post(url, json=_quote(atta), headers=owner).status_code == 201
    assert client.post(url, json=_quote(atta, unit_price=round(atta["mrp"] * 0.7, 2)), headers=owner).status_code == 201
    mine = [x for x in client.get("/api/distributors", headers=owner).json() if x["id"] == d["id"]][0]
    assert len(mine["quotes"]) == 1  # the new quote replaced the old one


def test_login_is_rate_limited_per_phone_even_for_unknown_numbers(client):
    body = {"phone": "9000000099", "password": "wrong-pass"}  # no such account
    for _ in range(5):
        assert client.post("/api/auth/login", json=body).status_code == 401
    r = client.post("/api/auth/login", json=body)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_good_login_resets_the_failure_count(client):
    bad = {"phone": "9000000004", "password": "wrong-pass"}
    for _ in range(3):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    assert client.post("/api/auth/login", json={"phone": "9000000004", "password": "vistaar123"}).status_code == 200
    for _ in range(3):  # 6 wrong tries in total, but the count restarted after the good login
        assert client.post("/api/auth/login", json=bad).status_code == 401

# ---- backdating, impact basis and the real-mohalla demo story ----

def _iso(days_ago):
    from datetime import date, timedelta
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _sell(client, h, pid, qty, **extra):
    return client.post("/api/sales", json={"product_id": pid, "qty": qty, **extra}, headers=h)


def test_backdated_sale_deducts_stock_counts_on_its_day_and_obeys_the_date_limits(client):
    h = _register_real(client, "9144444441")
    assert client.post("/api/stock/batches", headers=h, json={
        "product_name": "Backdate Test Rice", "category": "Staples", "qty": 100,
        "cost_price": 50, "sell_price": 60}).status_code == 201

    def row():
        return client.get("/api/stock", headers=h).json()[0]

    pid = row()["product_id"]

    # 30 days ago: stock goes down, but it is outside the 14-day rate window, so the daily rate stays 0
    assert _sell(client, h, pid, 28, sold_on=_iso(30)).status_code == 201
    assert row()["qty_left"] == 72 and row()["daily_rate"] == 0
    # 3 days ago: inside the window, 14 units / 14 days = 1.0 a day
    assert _sell(client, h, pid, 14, sold_on=_iso(3)).status_code == 201
    assert row()["qty_left"] == 58 and row()["daily_rate"] == 1.0
    # no date: still "now", and the response shape is unchanged
    now_sale = _sell(client, h, pid, 14)
    assert now_sale.status_code == 201 and set(now_sale.json()) == {"sale_ids", "qty"} and now_sale.json()["qty"] == 14
    assert row()["qty_left"] == 44 and row()["daily_rate"] == 2.0
    # today and exactly 60 days ago are fine
    assert _sell(client, h, pid, 1, sold_on=_iso(0)).status_code == 201
    assert _sell(client, h, pid, 1, sold_on=_iso(60)).status_code == 201
    assert row()["qty_left"] == 42

    # future and older than 60 days: 400 in Hinglish, nothing is deducted
    future = _sell(client, h, pid, 1, sold_on=_iso(-1))
    assert future.status_code == 400 and "Aane wali" in future.json()["detail"]
    too_old = _sell(client, h, pid, 1, sold_on=_iso(61))
    assert too_old.status_code == 400 and "60 din" in too_old.json()["detail"]
    # a backdated sale still cannot sell more than is on the shelf
    over = _sell(client, h, pid, 1000, sold_on=_iso(5))
    assert over.status_code == 400 and "Sirf 42" in over.json()["detail"]
    assert row()["qty_left"] == 42


def test_backdated_udhaar_entry_feeds_the_khata_draft_and_obeys_the_date_limits(client):
    h = _register_real(client, "9144444442")
    cid = client.post("/api/udhaar/customers", headers=h,
                      json={"name": "Backdate Customer", "phone": "9876500099"}).json()["id"]

    def entry(kind, amount, **extra):
        return client.post("/api/udhaar/entries", headers=h,
                           json={"customer_id": cid, "kind": kind, "amount": amount, **extra})

    def draft():
        return [d for d in client.get("/api/khata/drafts", headers=h).json() if d["customer_id"] == cid]

    first = entry("credit", 500, entry_date=_iso(20))
    assert first.status_code == 201 and first.json()["pending"] == 500
    assert first.json()["last_visit"] == _iso(0)  # a backdated entry never moves the last visit backwards
    assert [d["overdue_days"] for d in draft()] == [20]

    for bad in (_iso(-1), _iso(61)):
        r = entry("credit", 100, entry_date=bad)
        assert r.status_code == 400 and ("Aane wali" in r.json()["detail"] or "60 din" in r.json()["detail"])
    assert entry("credit", 100, entry_date=_iso(60)).status_code == 201  # exactly 60 days is fine
    assert entry("credit", 100).json()["pending"] == 700  # no date: today, same response as before

    assert entry("payment", 5000, entry_date=_iso(10)).status_code == 400  # more than is pending
    paid = entry("payment", 700, entry_date=_iso(10))
    assert paid.status_code == 201 and paid.json()["pending"] == 0
    assert draft() == []


def test_impact_basis_says_demo_only_for_demo_shops(client):
    demo = client.get("/api/impact", headers=_login(client)).json()
    assert "(demo)" in demo["pool"]["basis"]
    real = client.get("/api/impact", headers=_register_real(client, "9144444443")).json()
    assert "(demo)" not in real["pool"]["basis"] and real["simulated"] is False
    assert real["bulk"]["basis"] == demo["bulk"]["basis"]  # the savings assumption is labelled the same way


def test_demo_real_builds_the_whole_story_and_is_safe_to_rerun(client, monkeypatch):
    pytest.importorskip("httpx")
    from app import demo_real

    class UseTestClient:  # run the script against the in-process app, and do not close the shared client
        def __enter__(self):
            return client

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(demo_real, "make_client", lambda: UseTestClient())
    first = demo_real.main()
    assert first["checks"] == {"pulse spike": True, "sales drop": True, "khata draft": True, "swap suggestion": True}
    assert first["pulse"]["alerts"][0]["shops_spiking"] >= 4
    assert first["drop"]["drop"]["drop_pct"] >= 40 and first["drop"]["days_of_data"] >= 17
    assert first["khata"][0]["overdue_days"] == 20
    assert first["swaps_out"]["proposals"][0]["qty"] > 0
    assert "(demo)" not in first["impact"]["pool"]["basis"]

    def snapshot():
        out = {}
        for i in range(6):
            token = client.post("/api/auth/login", json={"phone": demo_real.phone(i), "password": demo_real.PASSWORD}).json()["token"]
            rows = client.get("/api/stock", headers={"Authorization": f"Bearer {token}"}).json()
            out[i] = sorted((r["product"], r["qty_left"]) for r in rows)
        return out

    before = snapshot()
    again = demo_real.main()  # second run: nothing is added twice
    assert snapshot() == before
    assert again["checks"] == first["checks"]
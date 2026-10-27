"""Build a small REAL (non-demo) mohalla through the public API, then run a bulk plan.

    python -m app.demo_real            # build the mohalla and print the plan
    python -m app.demo_real --approve  # also approve it and print the order

Uses only HTTP calls, exactly like the UI does: register 6 shops about 200 m apart, give each the same
products with stock and recent sales, add one distributor with quotes, then plan as shop 2. Safe to re-run:
existing shops are logged in instead of registered again, stock/sales are only added for new shops, and quotes
are refreshed each run.

Tip: pooled demand gets Laplace noise. For a stable demo set DP_EPSILON=20 in .env and restart the backend.
"""
import os
import sys
from datetime import date, timedelta

import httpx

BASE = os.getenv("VISTAAR_API", "http://localhost:8000").rstrip("/")
PASSWORD = "vistaar123"
LAT, LNG, STEP = 28.6139, 77.2090, 0.002  # ~220 m between shops
SHOPS = ["Sharma General Store", "Gupta Kirana", "Verma Provision", "Khan Mart", "Singh Traders", "Joshi Stores"]
# name, category, selling price (also becomes the MRP when the product is created), cost price
PRODUCTS = [
    ("Demo Atta 5kg", "Staples", 300.0, 240.0),
    ("Demo Sunflower Oil 1L", "Staples", 150.0, 120.0),
    ("Demo Glucose Biscuit 800g", "Biscuits", 80.0, 62.0),
]
DISTRIBUTOR = "Demo Real Wholesaler"
QUOTE_SHARE = 0.85  # quote price as a share of the selling price
QUOTE_MIN_QTY = 30


def phone(i: int) -> str:
    return f"91000000{i + 1:02d}"


def call(client: httpx.Client, method: str, path: str, token: str | None = None, ok=(200, 201), **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = client.request(method, BASE + path, headers=headers, timeout=30, **kw)
    if r.status_code not in ok:
        sys.exit(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def get_session(client: httpx.Client, i: int) -> tuple[str, bool]:
    """Return (token, is_new). Logs in if the shop exists, otherwise registers it."""
    r = client.post(BASE + "/api/auth/login", json={"phone": phone(i), "password": PASSWORD}, timeout=30)
    if r.status_code == 200:
        return r.json()["token"], False
    body = {"phone": phone(i), "name": f"Owner {i + 1}", "password": PASSWORD, "shop_name": SHOPS[i],
            "area": "Demo Mohalla", "lat": LAT + i * STEP, "lng": LNG, "upi_vpa": ""}
    return call(client, "POST", "/api/auth/register", json=body)["token"], True


def main(approve: bool = False) -> None:
    with httpx.Client() as client:
        tokens, new = [], []
        for i in range(len(SHOPS)):
            token, is_new = get_session(client, i)
            tokens.append(token)
            new.append(is_new)
        print(f"{sum(new)} new shop(s), {len(SHOPS) - sum(new)} existing.")

        # stock + recent sales, only for newly created shops so re-runs do not pile up data
        for i, token in enumerate(tokens):
            if not new[i]:
                continue
            for name, category, sell, cost in PRODUCTS:
                call(client, "POST", "/api/stock/batches", token, json={
                    "product_name": name, "category": category, "qty": 30, "cost_price": cost, "sell_price": sell})
            for name, *_ in PRODUCTS:
                pid = call(client, "GET", "/api/products", token, params={"q": name})[0]["id"]
                call(client, "POST", "/api/sales", token, json={"product_id": pid, "qty": 22 + i})  # ~25 left -> low

        # one distributor (added by shop 1) serves the whole real mohalla
        boss = tokens[0]
        dists = call(client, "GET", "/api/distributors", boss)
        dist = next((d for d in dists if d["name"] == DISTRIBUTOR), None)
        if dist is None:
            dist = call(client, "POST", "/api/distributors", boss, json={"name": DISTRIBUTOR})
        valid_till = str(date.today() + timedelta(days=5))
        for name, _cat, sell, _cost in PRODUCTS:
            pid = call(client, "GET", "/api/products", boss, params={"q": name})[0]["id"]
            call(client, "POST", f"/api/distributors/{dist['id']}/quotes", boss, json={
                "product_id": pid, "unit_price": round(sell * QUOTE_SHARE, 2), "min_qty": QUOTE_MIN_QTY,
                "delivery_days": 2, "valid_till": valid_till})
        print(f"Distributor '{DISTRIBUTOR}' has quotes for {len(PRODUCTS)} products (valid till {valid_till}).")

        plan = call(client, "POST", "/api/orders/plan", tokens[1])
        print(f"\nPlan for {SHOPS[1]}: cohort {plan['cohort_size']} shops, status {plan['status']}")
        if not plan["lines"]:
            print("No lines in the plan. Pooled demand is noisy: set DP_EPSILON=20 in .env, restart, and re-run.")
        for ln in plan["lines"]:
            print(f"  {ln.get('product', ln['product_id'])}: my qty {ln['my_qty']} @ Rs {ln['unit_price']}"
                  f"  (saving Rs {ln['my_saving']})")
        print(f"Estimated saving: Rs {plan['savings_estimate']}  [{plan['savings_basis']}]")
        if approve and plan["lines"]:
            done = call(client, "POST", f"/api/orders/{plan['thread_id']}/approve", tokens[1])
            print(f"Approved: orders {done['order_ids']}, audit hash {done['audit_hash'][:16]}...")
        print(f"\nLog in to the UI with phone {phone(1)} / password {PASSWORD} (any of {phone(0)}..{phone(5)}).")


if __name__ == "__main__":
    main(approve="--approve" in sys.argv)
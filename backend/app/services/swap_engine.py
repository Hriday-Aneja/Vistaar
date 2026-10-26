"""Mohalla Swap Engine: redistribute stock that will not sell in time to nearby shops running short.

Flow per suggestion run:
  1. Take every shop within radius of the asking shop (same demo/real world).
  2. Find expiry-risk batches (supply) and shops with low cover (demand), per product.
  3. Score every allowed pair (distance, expiry pressure, demand, margin) - see swap_scoring.
  4. Solve the assignment globally with min-cost flow (swap_solver).
  5. Return the proposals that involve the asking shop, as sender or receiver.
Nothing moves until the receiving shop approves (routers/swaps.py).
"""
from math import ceil, floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Batch, Product, Shop
from app.services.expiry import assess
from app.services.geo import haversine_km, nearby
from app.services.inventory import daily_rate, stock_on_hand
from app.services.swap_scoring import SHORTAGE_COVER_DAYS, score_swap
from app.services.swap_solver import solve
from app.services.worlds import same_world
from app.tuning import NEARBY_RADIUS_KM

TARGET_COVER_DAYS = 7
MIN_DAYS_LEFT = 2


def _empty(reason: str, message: str) -> dict:
    return {"proposals": [], "reason": reason, "message": message}


def suggest(db: Session, shop: Shop, today) -> dict:
    neighbours = nearby(shop, same_world(db, shop), NEARBY_RADIUS_KM)
    if not neighbours:
        return _empty("no_nearby_shops",
                      f"Aas-paas {NEARBY_RADIUS_KM:g} km me abhi koi aur Vistaar dukaan nahi judi hai.")

    group: dict[int, Shop] = {shop.id: shop, **{s.id: s for s, _ in neighbours}}
    rates: dict[tuple[int, int], float] = {}

    def rate_of(shop_id: int, product_id: int) -> float:
        if (shop_id, product_id) not in rates:
            rates[(shop_id, product_id)] = daily_rate(db, shop_id, product_id, today)
        return rates[(shop_id, product_id)]

    rows = db.execute(
        select(Batch, Product).join(Product, Batch.product_id == Product.id)
        .where(Batch.shop_id.in_(list(group)), Batch.qty_left > 0)
    ).all()

    # supplies: at-risk batches of any shop in the group, grouped by product
    risky: dict[int, list[tuple[Batch, Product, dict]]] = {}
    for batch, product in rows:
        risk = assess(batch.qty_left, rate_of(batch.shop_id, product.id), today, batch.expiry_date, batch.received_on)
        if risk["level"] in ("high", "medium") and risk["days_left"] >= MIN_DAYS_LEFT and risk["at_risk_qty"] > 0:
            risky.setdefault(product.id, []).append((batch, product, risk))
    if not risky:
        return _empty("no_risk_stock", "Abhi koi stock expiry ke risk me nahi hai.")

    proposals = []
    for product_id, items in risky.items():
        # demands: shops in the group that are about to run short of this product
        demands: dict[str, int] = {}
        info: dict[int, dict] = {}
        for sid in group:
            rate = rate_of(sid, product_id)
            if rate <= 0:
                continue
            stock = stock_on_hand(db, sid, product_id)
            cover = stock / rate
            if cover >= SHORTAGE_COVER_DAYS:
                continue
            need = ceil(rate * TARGET_COVER_DAYS - stock)
            if need > 0:
                demands[f"s{sid}"] = need
                info[sid] = {"rate": rate, "stock": stock, "cover": cover, "need": need}
        if not demands:
            continue

        supplies = {f"b{b.id}": risk["at_risk_qty"] for b, _, risk in items}
        by_batch = {f"b{b.id}": (b, p, risk) for b, p, risk in items}
        pairs: dict[tuple[str, str], tuple[float, int]] = {}
        for bk, (batch, _product, risk) in by_batch.items():
            for dk in demands:
                sid = int(dk[1:])
                if sid == batch.shop_id:
                    continue
                dist = haversine_km(group[batch.shop_id].lat, group[batch.shop_id].lng, group[sid].lat, group[sid].lng)
                if dist > NEARBY_RADIUS_KM:
                    continue
                d = info[sid]
                absorb = floor(d["rate"] * risk["days_left"] - d["stock"])
                cap = min(risk["at_risk_qty"], d["need"], absorb)
                if cap <= 0:
                    continue
                margin_pct = (batch.sell_price - batch.cost_price) / batch.sell_price
                score, _ = score_swap(dist, NEARBY_RADIUS_KM, risk["days_left"], d["cover"], cap / d["need"], margin_pct)
                pairs[(bk, dk)] = (score, cap)

        for bk, dk, qty in solve(supplies, demands, pairs):
            batch, product, risk = by_batch[bk]
            sid = int(dk[1:])
            if shop.id not in (batch.shop_id, sid):
                continue
            d = info[sid]
            dist = round(haversine_km(group[batch.shop_id].lat, group[batch.shop_id].lng, group[sid].lat, group[sid].lng), 2)
            margin_pct = (batch.sell_price - batch.cost_price) / batch.sell_price
            total, breakdown = score_swap(dist, NEARBY_RADIUS_KM, risk["days_left"], d["cover"], qty / d["need"], margin_pct)
            sender, receiver = group[batch.shop_id], group[sid]
            proposals.append({
                "role": "send" if sender.id == shop.id else "receive",
                "batch_id": batch.id, "product_id": product.id, "product": product.name, "qty": qty,
                "from_shop_id": sender.id, "from_shop": sender.name, "to_shop_id": receiver.id, "to_shop": receiver.name,
                "distance_km": dist, "days_left": risk["days_left"], "expiry_source": batch.expiry_source,
                "value_saved": round(qty * batch.cost_price, 2), "score": total, "breakdown": breakdown,
                "why": (f"{sender.name} ke {qty} {product.name} {risk['days_left']} din me expire honge, "
                        f"aur {receiver.name} me sirf {d['cover']:.1f} din ka stock bacha hai ({dist:.2f} km door)."),
            })

    proposals.sort(key=lambda item: item["score"], reverse=True)
    if not proposals:
        return _empty("no_match", "Paas ki dukaanon me is maal ki kami nahi hai, isliye abhi koi swap nahi bana.")
    return {"proposals": proposals, "reason": None, "message": None}

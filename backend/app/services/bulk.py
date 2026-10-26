"""Mohalla Bulk-Buy: DB-backed helpers used by the LangGraph pipeline (agents/graph.py)."""
from datetime import date, timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Distributor, DistributorQuote, Product, PurchaseOrder, Shop, utcnow
from app.services.audit_db import append_audit
from app.services.geo import nearby
from app.services.inventory import daily_rate, stock_on_hand
from app.services.price_radar import benchmark, flag_quote, run_reverse_auction
from app.services.pricing_rules import Quote, best_quote
from app.services.privacy import pool_demand
from app.services.worlds import same_world
from app.tuning import BULK_HORIZON_DAYS, NEARBY_RADIUS_KM, SOLO_PRICE_RATIO


def shop_needs(db: Session, shop_id: int, today: date, multiplier: float = 1.0) -> dict[int, int]:
    """product_id -> units to buy so stock lasts BULK_HORIZON_DAYS (x festival multiplier)."""
    needs: dict[int, int] = {}
    for product in db.scalars(select(Product)):
        rate = daily_rate(db, shop_id, product.id, today)
        if rate <= 0:
            continue
        need = ceil(rate * BULK_HORIZON_DAYS * multiplier - stock_on_hand(db, shop_id, product.id))
        if need > 0:
            needs[product.id] = need
    return needs


def build_cohort(db: Session, shop: Shop) -> list[Shop]:
    return [shop] + [s for s, _ in nearby(shop, same_world(db, shop), NEARBY_RADIUS_KM)]


def pooled_demand(per_shop: dict[int, dict[int, int]]) -> dict[int, int]:
    """Privacy-safe pooled quantity per product (k-anonymity gate + Laplace noise)."""
    st = get_settings()
    raw = pool_demand({str(s): {str(p): q for p, q in items.items()} for s, items in per_shop.items()},
                      k=st.k_anonymity_min, epsilon=st.dp_epsilon, clip=500)
    return {int(p): q for p, q in raw.items()}


def paid_price_history(db: Session, product_id: int, days: int = 30) -> list[float]:
    since = utcnow() - timedelta(days=days)
    prices = []
    for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.created_at >= since,
                                                     PurchaseOrder.status == "approved")):
        prices += [float(line["unit_price"]) for line in po.lines if line["product_id"] == product_id]
    return prices


def negotiate(db: Session, pooled: dict[int, int], today: date) -> tuple[list[dict], list[dict]]:
    """For each pooled product: eligible quotes (pooled qty unlocks min-qty), price-radar flags,
    reverse auction, then the deterministic margin guardrail. Returns (chosen, auction_events)."""
    st = get_settings()
    chosen, events = [], []
    for product_id, qty in pooled.items():
        product = db.get(Product, product_id)
        rows = db.execute(
            select(DistributorQuote, Distributor).join(Distributor, DistributorQuote.distributor_id == Distributor.id)
            .where(DistributorQuote.product_id == product_id, DistributorQuote.valid_till >= today,
                   DistributorQuote.min_qty <= qty)
        ).all()
        if not rows:
            continue
        bench = benchmark(paid_price_history(db, product_id))
        offers = {str(q.distributor_id): q.unit_price for q, _ in rows}
        floors = {str(q.distributor_id): round(q.unit_price * d.floor_ratio, 2) for q, d in rows}
        flags = {k: flag_quote(v, bench) for k, v in offers.items()}
        final, auction = run_reverse_auction(offers, floors)
        events += [{**e, "product_id": product_id, "product": product.name} for e in auction]

        meta = {str(q.distributor_id): (q, d) for q, d in rows}
        quotes = [Quote(k, str(product_id), price, meta[k][0].min_qty, meta[k][0].delivery_days)
                  for k, price in final.items()]
        pick = best_quote(quotes, product.mrp, st.min_margin_pct)
        if pick is None:
            continue
        q, d = meta[pick.distributor_id]
        solo = round(product.mrp * SOLO_PRICE_RATIO, 2)
        chosen.append({
            "product_id": product_id, "product": product.name, "pooled_qty": qty,
            "distributor_id": d.id, "distributor": d.name, "unit_price": pick.unit_price,
            "list_price": q.unit_price, "delivery_days": q.delivery_days, "solo_price_estimate": solo,
            "flag_on_list_price": flags[pick.distributor_id], "benchmark": bench,
        })
    return chosen, events


def place_orders(db: Session, shop_needs_by_shop: dict[int, dict[int, int]], chosen: list[dict],
                 thread_id: str) -> tuple[list[int], str]:
    """One PurchaseOrder per distributor; each participating shop gets its own real quantity."""
    by_dist: dict[int, list[dict]] = {}
    for c in chosen:
        by_dist.setdefault(c["distributor_id"], []).append(c)
    order_ids, last_hash = [], ""
    for dist_id, items in by_dist.items():
        lines = [{"product_id": c["product_id"], "shop_id": sid, "qty": needs[c["product_id"]],
                  "unit_price": c["unit_price"]}
                 for c in items for sid, needs in shop_needs_by_shop.items() if c["product_id"] in needs]
        po = PurchaseOrder(distributor_id=dist_id, lines=lines, status="approved", thread_id=thread_id,
                           total=round(sum(line["qty"] * line["unit_price"] for line in lines), 2),
                           approved_at=utcnow())
        db.add(po)
        db.flush()
        entry = append_audit(db, "purchase_order", po.id,
                             {"distributor_id": dist_id, "total": po.total, "lines": len(lines), "thread_id": thread_id})
        po.audit_hash = entry.hash
        order_ids.append(po.id)
        last_hash = entry.hash
    db.commit()
    return order_ids, last_hash

"""Creates Pulse / sales-drop alerts for the Celery monitors and pushes them to the shop's live channel.

A Pulse alert is saved as a PulseAlert row (once per shop and product per DEDUPE_HOURS) and then published as
{"event": "alert", "kind": "pulse", ...}. A sales drop belongs to the whole shop, not one product, and PulseAlert
needs a product, so it is only published ({"kind": "sales_drop"}); the daily task re-sends it while the drop lasts.
Events go only to the shop's own channel and carry only what that shop's own alerts API already shows.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PulseAlert, Shop, utcnow
from app.services import alert_bus

DEDUPE_HOURS = 24


def _pulse_event(row: PulseAlert, alert: dict) -> dict:
    return {
        "event": "alert", "kind": "pulse", "id": row.id, "shop_id": row.shop_id,
        "product_id": row.product_id, "product": alert["product"], "uplift": alert["uplift"],
        "title": f"{alert['product']} ki bikri aas-paas {alert['uplift']}x badhi",
        "action": row.action, "why": row.why, "created_at": row.created_at.isoformat(),
    }


def record_pulse_alerts(db: Session, shop: Shop, alerts: list[dict]) -> int:
    """Save the alerts that are new for this shop (no open one for the product in the last 24 h) and publish them
    after the commit, so a listener that reacts by calling the API already sees the row. Returns how many were new."""
    since = utcnow() - timedelta(hours=DEDUPE_HOURS)
    fresh: list[tuple[PulseAlert, dict]] = []
    for a in alerts:
        seen = db.scalar(select(PulseAlert.id).where(PulseAlert.shop_id == shop.id,
                                                     PulseAlert.product_id == a["product_id"],
                                                     PulseAlert.status == "open", PulseAlert.created_at >= since))
        if seen is not None:
            continue
        cause = a["cause"]["label"] if a.get("cause") else "Karan abhi pata nahi"
        row = PulseAlert(shop_id=shop.id, product_id=a["product_id"], z_score=a["max_z"], cause=cause[:200],
                         action=a["action"][:200], why=a["why"], status="open")
        db.add(row)
        fresh.append((row, a))
    if not fresh:
        return 0
    db.commit()
    for row, a in fresh:
        alert_bus.publish_alert(shop.id, _pulse_event(row, a))
    return len(fresh)


def publish_sales_drop(shop: Shop, result: dict) -> bool:
    drop = result.get("drop")
    if not drop:
        return False
    event = {
        "event": "alert", "kind": "sales_drop", "id": None, "shop_id": shop.id,
        "title": "Bikri gir rahi hai",
        "action": "Pata karo: koi maal khatam to nahi hua, ya dukaan band to nahi rahi?",
        "why": f"Pichhle {drop['recent_days']} din roz ~{drop['recent']} units bike, aam din ~{drop['baseline']} "
               f"({drop['drop_pct']}% kam).",
        "drop": drop, "through": result.get("through"), "created_at": utcnow().isoformat(),
    }
    return alert_bus.publish_alert(shop.id, event)

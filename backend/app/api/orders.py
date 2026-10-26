"""Mohalla Bulk-Buy API: plan (runs the LangGraph pipeline up to the approval gate) -> approve -> PO pdf."""
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.db.models import Distributor, Product, PurchaseOrder, Shop, User
from app.db.session import get_db
from app.deps import current_user
from app.tuning import SOLO_PRICE_RATIO

router = APIRouter(prefix="/api/orders", tags=["bulk-buy"])
_graph = build_graph()  # in-memory checkpointer; swap for Redis/Postgres later
_thread_owner: dict[str, int] = {}  # thread_id -> shop_id (who may approve)


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@router.post("/plan")
def plan(user: User = Depends(current_user)) -> dict:
    thread_id = uuid4().hex
    _thread_owner[thread_id] = user.shop_id
    state = _graph.invoke({"shop_id": user.shop_id}, _cfg(thread_id))
    lines = []
    for c in state["chosen"]:
        mine = state["needs_by_shop"].get(user.shop_id, {}).get(c["product_id"], 0)
        lines.append({**c, "my_qty": mine,
                      "my_saving": round(mine * (c["solo_price_estimate"] - c["unit_price"]), 2)})
    return {
        "thread_id": thread_id,
        "status": state["status"],
        "cohort_size": len(state["cohort_ids"]),
        "pooled_demand": [{"product_id": p, "qty": q} for p, q in state["pooled_demand"].items()],
        "lines": lines,
        "auction_log": state["auction_log"],
        "savings_estimate": round(sum(line["my_saving"] for line in lines), 2),
        "savings_basis": f"vs a lone kirana paying ~{SOLO_PRICE_RATIO * 100:.0f}% of MRP (assumption)",
    }


@router.post("/{thread_id}/approve")
def approve(thread_id: str, user: User = Depends(current_user)) -> dict:
    if _thread_owner.get(thread_id) != user.shop_id:
        raise HTTPException(404, "Plan nahi mila")
    state = _graph.invoke(None, _cfg(thread_id))  # resume past the approval gate
    return {"status": state["status"], "order_ids": state["order_ids"], "audit_hash": state["audit_hash"]}


@router.get("/{order_id}/po.pdf")
def po_pdf(order_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    from app.services.po_pdf import render_po_pdf

    po = db.get(PurchaseOrder, order_id)
    mine = [] if po is None else [ln for ln in po.lines if ln["shop_id"] == user.shop_id]
    if po is None or not mine:
        raise HTTPException(404, "Order nahi mila")
    lines = [{"product": db.get(Product, ln["product_id"]).name, "qty": ln["qty"], "unit_price": ln["unit_price"],
              "amount": round(ln["qty"] * ln["unit_price"], 2)} for ln in mine]
    order = {"order_id": po.id, "distributor": db.get(Distributor, po.distributor_id).name,
             "shop": db.get(Shop, user.shop_id).name, "cohort_size": len({ln["shop_id"] for ln in po.lines}),
             "lines": lines, "total": round(sum(ln["amount"] for ln in lines), 2), "audit_hash": po.audit_hash}
    return Response(render_po_pdf(order), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="PO-{po.id}.pdf"'})

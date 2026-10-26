"""Mohalla Bulk-Buy API: plan (runs the LangGraph pipeline up to the approval gate) -> approve -> PO pdf.

A plan is saved in the DB (PlanThread). Approve places the orders from that saved plan, so a pending plan
survives a server restart and cannot be approved twice."""
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.agents.graph import build_graph
from app.db.models import Distributor, PlanThread, Product, PurchaseOrder, Shop, User
from app.db.session import get_db
from app.deps import current_user
from app.services import bulk
from app.services.inventory import daily_rate, stock_on_hand
from app.services.reasons import FORECAST_METHOD, explain_need
from app.tuning import BULK_HORIZON_DAYS, SOLO_PRICE_RATIO

router = APIRouter(prefix="/api/orders", tags=["bulk-buy"])
_graph = build_graph()  # in-memory checkpointer: only used while planning, the saved plan lives in the DB


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@router.post("/plan")
def plan(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    thread_id = uuid4().hex
    state = _graph.invoke({"shop_id": user.shop_id}, _cfg(thread_id))
    db.add(PlanThread(thread_id=thread_id, shop_id=user.shop_id, status="planned", state={
        "needs_by_shop": state["needs_by_shop"], "chosen": state["chosen"],
        "auction_log": state["auction_log"], "festival_multiplier": state["festival_multiplier"]}))
    db.commit()
    lines = []
    for c in state["chosen"]:
        mine = state["needs_by_shop"].get(user.shop_id, {}).get(c["product_id"], 0)
        reason = None
        if mine > 0:
            reason = explain_need(daily_rate(db, user.shop_id, c["product_id"], date.today()),
                                  stock_on_hand(db, user.shop_id, c["product_id"]),
                                  BULK_HORIZON_DAYS, state["festival_multiplier"], mine)
        lines.append({**c, "my_qty": mine, "reason": reason,
                      "my_saving": round(mine * (c["solo_price_estimate"] - c["unit_price"]), 2)})
    return {
        "thread_id": thread_id,
        "status": state["status"],
        "cohort_size": len(state["cohort_ids"]),
        "pooled_demand": [{"product_id": p, "qty": q} for p, q in state["pooled_demand"].items()],
        "lines": lines,
        "auction_log": state["auction_log"],
        "savings_estimate": round(sum(line["my_saving"] for line in lines), 2),
        "forecast_method": FORECAST_METHOD,
        "savings_basis": f"vs a lone kirana paying ~{SOLO_PRICE_RATIO * 100:.0f}% of MRP (assumption)",
    }


@router.post("/{thread_id}/approve")
def approve(thread_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    row = db.get(PlanThread, thread_id)
    if row is None or row.shop_id != user.shop_id:
        raise HTTPException(404, "Plan nahi mila")
    if row.status == "ordered":  # approving twice returns the same orders instead of ordering again
        return {"status": "ordered", "order_ids": row.order_ids, "audit_hash": row.audit_hash}

    claimed = db.execute(update(PlanThread).where(PlanThread.thread_id == thread_id, PlanThread.status == "planned")
                         .values(status="ordering")).rowcount
    db.commit()
    if claimed != 1:
        raise HTTPException(409, "Ye plan abhi process ho raha hai")
    try:
        needs = {int(sid): {int(pid): qty for pid, qty in items.items()}
                 for sid, items in row.state["needs_by_shop"].items()}
        order_ids, audit_hash = bulk.place_orders(db, needs, row.state["chosen"], thread_id=thread_id)
    except Exception:
        db.rollback()
        db.execute(update(PlanThread).where(PlanThread.thread_id == thread_id).values(status="planned"))
        db.commit()
        raise
    row.status, row.order_ids, row.audit_hash = "ordered", order_ids, audit_hash
    db.commit()
    return {"status": "ordered", "order_ids": order_ids, "audit_hash": audit_hash}


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
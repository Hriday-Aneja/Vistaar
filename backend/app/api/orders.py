"""Mohalla Bulk-Buy API: plan (runs the LangGraph pipeline up to the approval gate) -> approve -> PO pdf."""
from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.models import (
    Distributor,
    OrderPlan,
    Product,
    PurchaseOrder,
    Shop,
    User,
)
from app.db.session import SessionLocal, get_db
from app.deps import current_user
from app.tuning import SOLO_PRICE_RATIO

router = APIRouter(prefix="/api/orders", tags=["bulk-buy"])



def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


@router.post("/plan")
def plan(
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    thread_id = uuid4().hex
    graph = request.app.state.order_graph

    # Persist ownership before starting the workflow.
    with SessionLocal() as db:
        db.add(
            OrderPlan(
                thread_id=thread_id,
                shop_id=user.shop_id,
                status="planning",
            )
        )
        db.commit()

    try:
        state = graph.invoke(
            {"shop_id": user.shop_id},
            _cfg(thread_id),
        )
    except Exception:
        with SessionLocal() as db:
            plan_record = db.get(OrderPlan, thread_id)
            if plan_record:
                plan_record.status = "failed"
                db.commit()
        raise

    with SessionLocal() as db:
        plan_record = db.get(OrderPlan, thread_id)
        if plan_record:
            plan_record.status = state.get(
                "status",
                "awaiting_approval",
            )
            db.commit()

    lines = []
    for c in state["chosen"]:
        mine = state["needs_by_shop"].get(
            user.shop_id, {}
        ).get(c["product_id"], 0)

        lines.append({
            **c,
            "my_qty": mine,
            "my_saving": round(
                mine * (
                    c["solo_price_estimate"] - c["unit_price"]
                ),
                2,
            ),
        })

    return {
        "thread_id": thread_id,
        "status": state["status"],
        "cohort_size": len(state["cohort_ids"]),
        "pooled_demand": [
            {"product_id": p, "qty": q}
            for p, q in state["pooled_demand"].items()
        ],
        "lines": lines,
        "auction_log": state["auction_log"],
        "savings_estimate": round(
            sum(line["my_saving"] for line in lines),
            2,
        ),
        "savings_basis": (
            f"vs a lone kirana paying "
            f"~{SOLO_PRICE_RATIO * 100:.0f}% of MRP (assumption)"
        ),
    }





@router.post("/{thread_id}/approve")
def approve(
    thread_id: str,
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    # Verify plan ownership from PostgreSQL
    with SessionLocal() as db:
        plan_record = db.get(OrderPlan, thread_id)

        if plan_record is None or plan_record.shop_id != user.shop_id:
            raise HTTPException(404, "Plan nahi mila")

        # If already completed, do not execute the workflow again
        if plan_record.status == "ordered":
            existing_orders = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.thread_id == thread_id)
                .all()
            )

            return {
                "status": "ordered",
                "order_ids": [order.id for order in existing_orders],
                "audit_hash": existing_orders[-1].audit_hash
                if existing_orders
                else None,
            }

        if plan_record.status != "awaiting_approval":
            raise HTTPException(
                409,
                f"Plan cannot be approved in status: {plan_record.status}",
            )

    # Resume the persisted LangGraph checkpoint
    graph = request.app.state.order_graph

    state = graph.invoke(
        None,
        _cfg(thread_id),
    )

    # Persist the final status
    with SessionLocal() as db:
        plan_record = db.get(OrderPlan, thread_id)

        if plan_record:
            plan_record.status = state.get("status", "ordered")
            db.commit()

    return {
        "status": state["status"],
        "order_ids": state.get("order_ids", []),
        "audit_hash": state.get("audit_hash"),
    }

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

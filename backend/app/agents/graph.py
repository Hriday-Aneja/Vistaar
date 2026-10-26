"""Vistaar bulk-buy pipeline (LangGraph).

forecast -> cohort -> negotiate -> [merchant approval] -> place_order

The graph pauses before `place_order`. Nothing is ordered until the merchant approves
(resume with graph.invoke(None, config)).
"""
from datetime import date

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.state import OrderState
from app.db.models import Shop
from app.db.session import SessionLocal
from app.services import bulk

FESTIVAL_MULTIPLIER = 1.3  # demo: pre-festival demand bump


def forecast_node(state: OrderState) -> OrderState:
    mult = state.get("festival_multiplier", FESTIVAL_MULTIPLIER)
    with SessionLocal() as db:
        needs = bulk.shop_needs(db, state["shop_id"], date.today(), mult)
    return {"festival_multiplier": mult, "needs_by_shop": {state["shop_id"]: needs}, "status": "forecasted"}


def cohort_node(state: OrderState) -> OrderState:
    mult = state["festival_multiplier"]
    with SessionLocal() as db:
        cohort = bulk.build_cohort(db, db.get(Shop, state["shop_id"]))
        needs_by_shop = {s.id: bulk.shop_needs(db, s.id, date.today(), mult) for s in cohort}
    pooled = bulk.pooled_demand(needs_by_shop)
    return {"cohort_ids": [s.id for s in cohort], "needs_by_shop": needs_by_shop,
            "pooled_demand": pooled, "status": "pooled"}


def negotiate_node(state: OrderState) -> OrderState:
    with SessionLocal() as db:
        demo = db.get(Shop, state["shop_id"]).is_demo  # real shops only negotiate with real distributors
        chosen, events = bulk.negotiate(db, state["pooled_demand"], date.today(), demo=demo)
    return {"chosen": chosen, "auction_log": events, "status": "awaiting_approval"}


def place_order_node(state: OrderState) -> OrderState:
    with SessionLocal() as db:
        order_ids, audit_hash = bulk.place_orders(db, state["needs_by_shop"], state["chosen"],
                                                  thread_id=str(state.get("shop_id")))
    return {"order_ids": order_ids, "audit_hash": audit_hash, "status": "ordered"}


def build_graph(checkpointer=None):
    g = StateGraph(OrderState)
    g.add_node("forecast", forecast_node)
    g.add_node("cohort", cohort_node)
    g.add_node("negotiate", negotiate_node)
    g.add_node("place_order", place_order_node)

    g.add_edge(START, "forecast")
    g.add_edge("forecast", "cohort")
    g.add_edge("cohort", "negotiate")
    g.add_edge("negotiate", "place_order")
    g.add_edge("place_order", END)

    return g.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["place_order"],  # human-in-the-loop approval gate
    )
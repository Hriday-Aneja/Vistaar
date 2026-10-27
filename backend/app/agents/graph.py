
"""Vistaar bulk-buy pipeline (LangGraph).

forecast -> cohort -> negotiate -> [merchant approval] -> place_order
"""

from datetime import date
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.state import OrderState
from app.db.models import Shop
from app.db.session import SessionLocal
from app.services import bulk

FESTIVAL_MULTIPLIER = 1.3


def forecast_node(state: OrderState) -> OrderState:
    mult = state.get("festival_multiplier", FESTIVAL_MULTIPLIER)
    with SessionLocal() as db:
        needs = bulk.shop_needs(db, state["shop_id"], date.today(), mult)
    return {
        "festival_multiplier": mult,
        "needs_by_shop": {state["shop_id"]: needs},
        "status": "forecasted",
    }


def cohort_node(state: OrderState) -> OrderState:
    mult = state["festival_multiplier"]
    with SessionLocal() as db:
        cohort = bulk.build_cohort(db, db.get(Shop, state["shop_id"]))
        needs_by_shop = {
            shop.id: bulk.shop_needs(db, shop.id, date.today(), mult)
            for shop in cohort
        }
    pooled = bulk.pooled_demand(needs_by_shop)
    return {
        "cohort_ids": [shop.id for shop in cohort],
        "needs_by_shop": needs_by_shop,
        "pooled_demand": pooled,
        "status": "pooled",
    }


def negotiate_node(state: OrderState) -> OrderState:
    with SessionLocal() as db:
        # real shops only negotiate with real distributors
        demo = db.get(Shop, state["shop_id"]).is_demo
        chosen, events = bulk.negotiate(
            db,
            state["pooled_demand"],
            date.today(),
            demo=demo,
        )
    return {
        "chosen": chosen,
        "auction_log": events,
        "status": "awaiting_approval",
    }

def place_order_node(
    state: OrderState,
    config: RunnableConfig,
) -> OrderState:
    thread_id = config["configurable"]["thread_id"]

    with SessionLocal() as db:
        order_ids, audit_hash = bulk.place_orders(
            db,
            state["needs_by_shop"],
            state["chosen"],
            thread_id=thread_id,
        )

    return {
        "order_ids": order_ids,
        "audit_hash": audit_hash,
        "status": "ordered",
    }


def build_graph(checkpointer=None):
    graph = StateGraph(OrderState)
    graph.add_node("forecast", forecast_node)
    graph.add_node("cohort", cohort_node)
    graph.add_node("negotiate", negotiate_node)
    graph.add_node("place_order", place_order_node)

    graph.add_edge(START, "forecast")
    graph.add_edge("forecast", "cohort")
    graph.add_edge("cohort", "negotiate")
    graph.add_edge("negotiate", "place_order")
    graph.add_edge("place_order", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["place_order"],
    )

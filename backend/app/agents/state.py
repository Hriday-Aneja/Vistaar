from typing import TypedDict


class OrderState(TypedDict, total=False):
    shop_id: int
    festival_multiplier: float
    needs_by_shop: dict[int, dict[int, int]]  # shop_id -> {product_id: units}  (internal, never shown)
    forecast_methods: dict[int, str]          # shop_id -> "xgboost+shap" | "rule-based"
    cohort_ids: list[int]
    pooled_demand: dict[int, int]             # product_id -> noisy pooled units (k-anonymous)
    chosen: list[dict]                        # best acceptable quote per product
    auction_log: list[dict]
    status: str
    order_ids: list[int]
    audit_hash: str

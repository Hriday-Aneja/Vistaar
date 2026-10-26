"""Deterministic pricing guardrails. The LLM can suggest; these rules decide."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    distributor_id: str
    sku: str
    unit_price: float
    min_qty: int
    delivery_days: int


def margin_pct(retail_price: float, unit_price: float) -> float:
    return (retail_price - unit_price) / retail_price * 100


def is_acceptable(quote: Quote, retail_price: float, min_margin_pct: float) -> bool:
    return margin_pct(retail_price, quote.unit_price) >= min_margin_pct


def best_quote(quotes: list[Quote], retail_price: float, min_margin_pct: float) -> Quote | None:
    ok = [q for q in quotes if is_acceptable(q, retail_price, min_margin_pct)]
    if not ok:
        return None
    return min(ok, key=lambda q: (q.unit_price, q.delivery_days))


def clamp_counter_offer(current_price: float, proposed_price: float, max_discount_pct: float) -> float:
    """Never ask for more than max_discount_pct below the current price."""
    floor = current_price * (1 - max_discount_pct / 100)
    return round(max(proposed_price, floor), 2)

# Architecture

```
Merchant (Next.js, mobile-first)
        |  Bearer token
   FastAPI /api/*
   |-- auth, stock, shops
   |-- orders  --> LangGraph: forecast -> cohort -> negotiate -> [approval gate] -> place_order
   |                 |           |           |
   |            inventory     privacy     price_radar (benchmark, flags, reverse auction)
   |            (sales rate)  (k-anon + DP)  + pricing_rules (margin guardrail)
   |-- swaps   --> swap_engine -> swap_scoring + swap_solver (min-cost flow)
   |-- udhaar  --> name_matching -> trust (cross-shop view) -> privacy (keyed hash + noise) + trust_scoring
   |-- khata   --> reminders + upi (draft, then merchant sends)
   |-- pulse   --> pulse_stats (z-score) + event calendar
   |-- prices  --> price_radar
   |
   PostgreSQL (PostGIS image)    audit_log (hash chain)    Celery + Redis (hourly pulse monitor)
```

## Swap Engine in one paragraph

For each product, every shop within the radius contributes expiry-risk batches (supply) and every shop with low cover contributes a shortage (demand). Each allowed pair gets a 0-100 score from distance, expiry pressure, demand fit and margin. A min-cost-flow solver then picks the assignment that maximises total score without double-sending stock or overfilling a shop. Only proposals involving the asking shop are shown. The receiving shop approves; stock moves and the decision is audited.

## Key decisions

- **Human in the loop everywhere money or stock moves.**
- **Deterministic money logic** in `pricing_rules.py`.
- **Privacy:** k-anonymity + Laplace noise for pooled demand; keyed hash + per-day deterministic noise for udhaar. Prototype-grade; production needs private set intersection.
- **Resilience:** `llm.py` falls back across providers.
- **Demo vs real shops** are separated by `shops.is_demo`.

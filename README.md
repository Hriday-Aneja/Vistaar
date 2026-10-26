# Vistaar

AI business teammate for Indian kirana merchants (Paytm hackathon, Track 1: Merchant Growth AI).

One loop: **buy together, swap surplus, lend safely.**

## Features

| Feature | What it does | Where |
|---|---|---|
| **Mohalla Bulk-buy** | Forecasts each shop's need, pools nearby shops (k-anonymity + noise), unlocks distributor minimums, runs a reverse auction, merchant approves, PO PDF | `agents/graph.py`, `services/bulk.py`, `api/orders.py` |
| **Mohalla Swap Engine** | Moves stock that will not sell before expiry to nearby shops running short. Global min-cost-flow matching, scored on distance, expiry pressure, demand and margin, with a visible score breakdown | `services/swap_engine.py`, `swap_solver.py`, `swap_scoring.py` |
| **Udhaar Trust Network** | Merchant asks "Rahul ko udhaar du?"; gets a risk level and credit limit built from nearby shops without seeing their private history. Shows "not enough data" instead of guessing | `services/trust.py`, `trust_scoring.py`, `privacy.py`, `name_matching.py` |
| **Khata reminders** | Drafts polite Hinglish reminders with a UPI link; sends only after the merchant approves | `api/khata.py`, `services/reminders.py` |
| **Mohalla Pulse** | Detects a same-time sales spike across neighbouring shops, matches it to an event calendar, suggests extra stock | `services/pulse.py`, `pulse_stats.py` |
| **Fair-Price Radar** | Compares each distributor quote with what other pools actually paid (median, k-anonymous), flags inflated quotes, runs a reverse auction | `services/price_radar.py`, `api/prices.py` |
| Stock and expiry | Batches, expiry risk with a plain-language "kyun?", sales entry | `api/stock.py`, `services/expiry.py` |

The first prototype of the swap, udhaar, pulse and stock screens came from a teammate's standalone version; it is merged here onto the team stack.

## Stack

FastAPI, SQLAlchemy, PostgreSQL (PostGIS image), LangGraph, Celery + Redis, Next.js (App Router, TypeScript), OpenLayers, WeasyPrint, Docker. LLM fallback chain: Gemini, Groq, offline rules. Optional later: Neo4j, Qdrant (`--profile full`).

## Quick start

```bash
cp .env.example .env
docker compose up --build
# in another terminal, load demo data:
make seed
```

- Frontend: http://localhost:3000 (login `9000000001` / `vistaar123`; shops `...02` to `...06` share the password)
- API docs: http://localhost:8000/docs

Quick local run without Docker: set `DATABASE_URL=sqlite:///./vistaar.db`, then `cd backend && pip install -r requirements.txt && python -m app.seed && uvicorn app.main:app --reload`.

Tests: `cd backend && pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`

## Demo story (all in the seed data)

1. **Sharma General Store** has 140 Marie Gold biscuits expiring in 9 days, but sells about 2 a day. **Gupta Kirana** sells about 9 a day and has 10 left. Open **Swap**: Vistaar proposes the transfer and shows why.
2. Three shops see ice cream sales jump together. Open **Pulse** as Singh Provision Store (`9000000003`): heatwave spike, with an order suggestion.
3. **Udhaar**: type "Rahul bhai ko udhaar du?". Two Rahuls, so it asks which one. For Rahul Verma it shows a risk level from three other shops. Mohan Lal has no network data, so it says so.
4. **Bulk-buy**: "Diwali ka maal plan karo" pools the mohalla, runs the auction, then Approve and open the PO.
5. **Daam**: Sai Distributors' atta quote is flagged as above what other pools paid.

## Layout

```
backend/app/
  api/        FastAPI routers (auth, stock, orders, swaps, udhaar, khata, pulse, prices, shops)
  agents/     LangGraph bulk-buy pipeline
  services/   business logic (pure modules are unit-tested without a DB)
  db/         SQLAlchemy session + models
  workers/    Celery app and scheduled tasks
  seed.py     demo data
  tuning.py   env-tunable constants
backend/tests/
frontend/src/ Next.js pages (bulk, stock, swaps, udhaar, pulse, prices, map), components, lib
infra/        init.sql (enables PostGIS)
docs/         architecture, roadmap, notes
```

## Design rules

1. The merchant approves every important action (the pipeline pauses before `place_order`; swaps and reminders need explicit approval).
2. Prices, margins and discount caps are decided by code (`pricing_rules.py`), never by the LLM.
3. A cross-shop number is only shown when enough shops contributed, with noise added.
4. Every order, swap and reminder is written to a hash-chained audit log (`/health` verifies it).
5. Simulated data is labelled; the demo event calendar is not real weather or match data.

## Team split (2 people)

- **A (backend + AI):** swap solver, trust model, forecast, auction, Celery, privacy.
- **B (frontend + data + pitch):** Next.js screens, map, seed story, demo, deck.

See `docs/roadmap.md`.

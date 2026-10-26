#!/usr/bin/env sh
# Usage: sh scripts/first_commit.sh
set -e
git init -b main
git add .
git commit -m "feat: merge swap, udhaar, pulse and fair-price features into the Vistaar monorepo" \
  -m "- FastAPI + SQLAlchemy/Postgres backend, LangGraph bulk-buy pipeline with approval gate
- Mohalla Swap Engine (min-cost-flow matching), Udhaar Trust Network, Khata reminders
- Mohalla Pulse and Fair-Price Radar (benchmark, flags, reverse auction)
- Privacy layer, hash-chained audit log, pricing guardrails, LLM fallback router
- Next.js frontend: bulk-buy, stock, swaps, udhaar, pulse, prices, map
- Docker Compose, Celery worker/beat, CI, seed data and unit tests"
git log --oneline -1

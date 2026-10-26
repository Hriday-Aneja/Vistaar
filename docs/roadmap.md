# Roadmap

## Done
- [x] Monorepo: FastAPI, SQLAlchemy/Postgres, LangGraph, Celery, Next.js, Docker Compose, CI
- [x] Bulk-buy pipeline on DB data with approval gate, PO PDF, hash-chained audit
- [x] Swap Engine with min-cost-flow matching
- [x] Udhaar Trust Network, name matching, khata reminder drafts
- [x] Mohalla Pulse (z-score + demo event calendar)
- [x] Fair-Price Radar (benchmark, flags, reverse auction)
- [x] Privacy layer, LLM fallback router, unit tests for all pure logic

## Next (priority order)
1. [ ] Run `docker compose up --build` end to end; fix whatever breaks (the DB-backed paths and the frontend were not executed when this was merged)
2. [ ] Live auction/negotiation events over Redis Pub/Sub -> WebSocket (`api/stream.py`)
3. [ ] XGBoost forecast + SHAP reasons in the bulk plan
4. [ ] PostGIS `ST_DWithin` for cohorts instead of Python haversine
5. [ ] Impact screen: savings, shops joined, udhaar recovered, expiry waste avoided
6. [ ] Real event/weather source for Pulse; shelf-photo stock count (YOLOv8)
7. [ ] Hinglish chat UI and Sarvam voice
8. [ ] Private set intersection for udhaar; DPDP consent flow
9. [ ] Demo script and deck

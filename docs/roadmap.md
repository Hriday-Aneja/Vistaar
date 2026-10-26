# Roadmap

## Done
- [x] Monorepo: FastAPI, SQLAlchemy/Postgres, LangGraph, Celery, Next.js, Docker Compose, CI
- [x] Bulk-buy pipeline on DB data with approval gate, PO PDF, hash-chained audit
- [x] Swap Engine with min-cost-flow matching
- [x] Udhaar Trust Network, name matching, khata reminder drafts
- [x] Mohalla Pulse (z-score + demo event calendar)
- [x] Fair-Price Radar (benchmark, flags, reverse auction)
- [x] Privacy layer, LLM fallback router (written, not used by any feature yet), unit tests for all pure logic
- [x] Bulk plan saved in the DB (survives a restart, cannot be approved twice, only the owner can approve)
- [x] Live auction panel: `/ws/negotiation/{thread_id}` replays the saved auction log (not Redis yet)
- [x] Rule-based reasons for each bulk quantity (not ML)
- [x] Impact screen and `/api/impact`, with simulation labels
- [x] Sales-drop alert (API, Pulse page card, daily Celery task) with a seeded demo shop
- [x] Live Pulse and sales-drop alerts over Redis Pub/Sub (`alerts:{shop_id}`, `/ws/alerts`, toast and card on the Pulse page, 30 s polling when Redis is down); the auction replay is unchanged
- [x] Hinglish chat page (keyword routing, no LLM)
- [x] `make reset-demo`
- [x] Name matching accepts nickname objects (fix)
- [x] Real and demo data separated for distributors, quotes, price history and the event calendar; owner-entered distributors and quotes
- [x] Login and registration rate limits, startup refusal for default secrets outside dev, CORS from config

## Next (priority order)
1. [ ] Run `docker compose up --build` end to end; fix whatever breaks (the DB-backed paths and the frontend were not executed when this was merged)
2. [ ] Run the API tests (`tests/test_api_flow.py`) and fix what fails
3. [ ] Live auction events over Redis Pub/Sub instead of replaying a saved log
4. [x] XGBoost forecast + SHAP reasons in the bulk plan (`services/ml_forecast.py`); the rule-based forecast stays as the fallback
5. [ ] PostGIS `ST_DWithin` for cohorts instead of Python haversine
6. [ ] Real event/weather source for Pulse; shelf-photo stock count (YOLOv8)
7. [ ] Sarvam voice; real WhatsApp sending; send the PO to the distributor
8. [ ] Phone OTP; move the login limiter to Redis if the API runs as more than one process
9. [ ] Private set intersection for udhaar; DPDP consent flow; pool opt-in
10. [ ] Demo script and deck (numbers labelled "projected (simulation)")
.PHONY: up down logs seed reset-demo test fmt

up:
	cp -n .env.example .env || true
	docker compose up --build

down:
	docker compose down

seed:
	docker compose exec backend python -m app.seed

reset-demo:
	docker compose exec backend python -m app.reset_demo

logs:
	docker compose logs -f backend worker

test:
	cd backend && python -m pytest -q

fmt:
	cd backend && python -m ruff format . && python -m ruff check . --fix
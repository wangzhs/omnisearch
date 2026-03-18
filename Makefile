up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

api:
	uvicorn app.main:app --reload --port $${API_PORT:-8000}

sync:
	python -m app.scripts.sync_stock --tickers "$${TICKERS}" $${REFRESH:+--refresh} $${PRICE_LIMIT:+--price-limit $${PRICE_LIMIT}} $${EVENT_LIMIT:+--event-limit $${EVENT_LIMIT}}

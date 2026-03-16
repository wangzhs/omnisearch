up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

api:
	uvicorn app.main:app --reload --port $${API_PORT:-8000}

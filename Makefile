.PHONY: dev seed test lint up down
dev:
	uvicorn app.main:app --reload
seed:
	python -m scripts.seed
test:
	pytest --cov=app
lint:
	ruff check app tests scripts
up:
	docker compose up --build -d
down:
	docker compose down


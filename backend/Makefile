.PHONY: install format lint typecheck test dev

install:
	python -m pip install -r requirements.txt

format:
	black app tests

lint:
	ruff check app tests

typecheck:
	mypy app

test:
	pytest

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

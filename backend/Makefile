.PHONY: install dev worker check test
install:
	uv sync
dev:
	uv run uvicorn src.gateway.app:app --host 127.0.0.1 --port 8001
worker:
	uv run python -m src.tools.worker
check:
	uv run python ../scripts/check_structure.py
test:
	uv run pytest tests

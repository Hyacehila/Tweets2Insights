.PHONY: install dev stop check test
install:
	uv sync --project backend
	npm --prefix frontend install
dev:
	uv run --project backend python scripts/dev.py start
stop:
	uv run --project backend python scripts/dev.py stop
check:
	uv run --project backend python scripts/check_structure.py
	npm --prefix frontend run check
test:
	uv run --project backend pytest backend/tests

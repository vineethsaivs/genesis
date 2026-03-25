.PHONY: install dev test lint format clean

install:
	uv sync

dev:
	uv run uvicorn backend.main:app --reload --port 8000

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check backend/ tests/

format:
	uv run ruff format backend/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache

.PHONY: install dev test lint format clean build

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short --cov=glidercure --cov-report=term-missing

lint:
	ruff check glidercure/ tests/

format:
	ruff check --fix glidercure/ tests/
	ruff format glidercure/ tests/

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

build:
	python -m build

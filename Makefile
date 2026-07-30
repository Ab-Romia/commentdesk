.PHONY: install lint typecheck test check

install:
	uv sync --all-extras

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest

check: lint typecheck test

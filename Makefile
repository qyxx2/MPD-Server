PYTHON ?= python3

.PHONY: test lint typecheck build

test:
	PYTHONPATH=. $(PYTHON) -m pytest server/tests

lint:
	$(PYTHON) -m ruff check server

typecheck:
	npm --prefix web run typecheck

build:
	npm --prefix web run build

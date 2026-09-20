VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help setup dev api web test lint build serve demo clean

help:
	@echo "make setup   install backend and frontend dependencies"
	@echo "make dev     run the API and the Vite dev server together"
	@echo "make api     run the API alone on :8000"
	@echo "make web     run the Vite dev server alone on :5173"
	@echo "make test    run the backend test suite"
	@echo "make lint    ruff on the backend, tsc on the frontend"
	@echo "make build   build the frontend into frontend/dist"
	@echo "make serve   build the frontend, then serve everything from :8000"
	@echo "make demo    rebuild the bundled demo digest from its source"

setup:
	python3 -m venv $(VENV)
	$(PIP) install -q -r backend/requirements-dev.txt
	cd frontend && npm install

dev:
	@$(MAKE) api & $(MAKE) web; wait

api:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && ../$(PY) -m pytest -q

lint:
	cd backend && ../$(VENV)/bin/ruff check app tests
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

serve: build
	cd backend && ../$(PY) -m uvicorn app.main:app --port 8000

demo:
	$(PY) data/demo/build_demo.py

clean:
	rm -rf .cache frontend/dist backend/.pytest_cache backend/.ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

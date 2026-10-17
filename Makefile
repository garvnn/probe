PY ?= .venv/bin/python

.PHONY: dev test mock

dev:  ## API with autoreload (DEMO_MODE from .env, default mock)
	$(PY) -m uvicorn backend.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

mock:  ## API serving fixtures only, for frontend development
	DEMO_MODE=mock $(PY) -m uvicorn backend.main:app --reload --port 8000

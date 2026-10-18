PY ?= .venv/bin/python

.PHONY: dev test mock web types

dev:  ## API with autoreload (DEMO_MODE from .env, default mock)
	$(PY) -m uvicorn backend.main:app --reload --port 8000

test:
	$(PY) -m pytest -q

mock:  ## API serving fixtures only, for frontend development
	DEMO_MODE=mock $(PY) -m uvicorn backend.main:app --reload --port 8000

web:  ## Next.js frontend on :3000 (run `make mock` or `make dev` alongside)
	cd probe-frontend && npm run dev

types:  ## Regenerate probe-frontend/lib/api-types.ts from the running API's /openapi.json
	cd probe-frontend && npm run gen:api

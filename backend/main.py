"""FastAPI app. Run with `make dev` or `uvicorn backend.main:app`."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import demo_mode
from backend.routes import blind_leak, breaking_point, contract, fake_data, fraud_checks, report, test_attacker, trials

app = FastAPI(title="Probe", description="Penetration testing for clinical trials.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotImplementedError)
async def not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
    """Stubs raise NotImplementedError("owner: <name>"); surface that as 501 instead of a 500."""
    return JSONResponse(status_code=501, content={"detail": str(exc) or "not implemented"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "demo_mode": demo_mode()}


for module in (trials, fake_data, fraud_checks, test_attacker, blind_leak, contract, breaking_point, report):
    app.include_router(module.router)

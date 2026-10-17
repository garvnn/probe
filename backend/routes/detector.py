from __future__ import annotations

from fastapi import APIRouter

from backend.models import HardenRequest, HardenResult
from backend.routes._mode import serve

router = APIRouter(prefix="/detector", tags=["detector"])
OWNER = "Shreyas"


@router.post("/harden", response_model=HardenResult)
def harden(body: HardenRequest) -> HardenResult:
    """Submit escaped fakes, get a new detector version (engine.harden.gate.accept_check)."""
    return serve("harden", HardenResult, OWNER)

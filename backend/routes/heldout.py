from __future__ import annotations

from fastapi import APIRouter

from backend.models import HeldoutRequest, HeldoutResult
from backend.routes._mode import serve

router = APIRouter(prefix="/heldout", tags=["heldout"])
OWNER = "Shreyas"


@router.post("/eval", response_model=HeldoutResult)
def heldout_eval(body: HeldoutRequest) -> HeldoutResult:
    """Run attacker B (never seen during hardening) against each detector version."""
    return serve("heldout", HeldoutResult, OWNER)

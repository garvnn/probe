from __future__ import annotations

from fastapi import APIRouter

from backend.models import PatchRequest, PatchResult
from backend.routes._mode import serve

router = APIRouter(prefix="/fraud-checks", tags=["fraud-checks"])
OWNER = "Shreyas"


@router.post("/patch", response_model=PatchResult)
def patch(body: PatchRequest) -> PatchResult:
    """Submit escaped fakes, get a new check-suite version (engine.patch.gate.accept_check)."""
    return serve("patch", PatchResult, OWNER)

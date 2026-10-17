from __future__ import annotations

from fastapi import APIRouter

from backend.models import MarginRequest, MarginResult
from backend.routes._mode import serve

router = APIRouter(tags=["margin"])
OWNER = "Garv"


@router.post("/margin", response_model=MarginResult)
def margin(body: MarginRequest) -> MarginResult:
    """Integrity margin curve for one detector version (engine.analysis.margin.integrity_margin)."""
    return serve("margin", MarginResult, OWNER, trial_id=body.trial_id, detector_version=body.detector_version)

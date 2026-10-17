from __future__ import annotations

from fastapi import APIRouter

from backend.models import BreakingPointRequest, BreakingPointResult
from backend.routes._mode import serve

router = APIRouter(tags=["breaking-point"])
OWNER = "Garv"


@router.post("/breaking-point", response_model=BreakingPointResult)
def breaking_point(body: BreakingPointRequest) -> BreakingPointResult:
    """Breaking-point curve for one check-suite version (engine.analysis.breaking_point.breaking_point)."""
    return serve("breaking_point", BreakingPointResult, OWNER, trial_id=body.trial_id, suite_version=body.suite_version)

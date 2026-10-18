from __future__ import annotations

from fastapi import APIRouter

from backend.models import PatchRequest, PatchResult
from backend.routes._mode import serve

router = APIRouter(prefix="/fraud-checks", tags=["fraud-checks"])
OWNER = "Shreyas"


@router.post("/patch", response_model=PatchResult)
def patch(body: PatchRequest) -> PatchResult:
    """Submit escaped fakes, get a new check-suite version (engine.patch.gate.accept_check)."""
    return serve("patch", PatchResult, OWNER, trial_id=body.trial_id, run_id=body.run_id, suite_version=body.suite_version)


@router.get("/held-out")
def held_out(trial_id: str = "tr_2026_B") -> dict:
    """Frozen Patch evaluation, not the separate different-model Stranger test."""
    from fastapi import HTTPException
    from backend.cached import load_response
    from backend.config import demo_mode

    if demo_mode() == "cached":
        result = load_response("patch_held_out", {"trial_id": trial_id})
        if result is not None:
            return result
    raise HTTPException(status_code=404, detail="no measured Patch held-out cache; run precompute_demo")

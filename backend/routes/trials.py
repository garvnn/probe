from __future__ import annotations

from fastapi import APIRouter

from backend.models import TrialCreate, TrialDetail, TrialSummary
from backend.routes._mode import serve

router = APIRouter(prefix="/trials", tags=["trials"])
OWNER = "Garv"


@router.post("", response_model=TrialSummary)
def create_trial(body: TrialCreate) -> TrialSummary:
    """Generate a trial from config (engine.generator.trial.generate_trial)."""
    return serve("trial_summary", TrialSummary, OWNER)


@router.get("/{trial_id}", response_model=TrialDetail)
def get_trial(trial_id: str) -> TrialDetail:
    """Summary + role matrix."""
    return serve("trial_detail", TrialDetail, OWNER, trial_id=trial_id)

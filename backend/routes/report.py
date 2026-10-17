from __future__ import annotations

from fastapi import APIRouter

from backend.models import Report
from backend.routes._mode import serve

router = APIRouter(prefix="/report", tags=["report"])
OWNER = "Ajay"


@router.get("/{trial_id}", response_model=Report)
def get_report(trial_id: str) -> Report:
    """One-page pentest report organized by the Integrity Contract."""
    return serve("report", Report, OWNER, trial_id=trial_id)

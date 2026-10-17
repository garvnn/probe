from __future__ import annotations

from fastapi import APIRouter

from backend.models import TestAttackerRequest, TestAttackerResult
from backend.routes._mode import serve

router = APIRouter(prefix="/test-attacker", tags=["test-attacker"])
OWNER = "Shreyas"


@router.post("/eval", response_model=TestAttackerResult)
def test_attacker_eval(body: TestAttackerRequest) -> TestAttackerResult:
    """Run the test attacker (never seen during patching) against each check-suite version."""
    return serve("test_attacker", TestAttackerResult, OWNER)

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from backend.models import ContractResponse
from backend.routes._mode import serve

router = APIRouter(prefix="/contract", tags=["contract"])
OWNER = "Ajay"


@router.get("/{trial_id}", response_model=ContractResponse)
def get_contract(trial_id: str, fixture: Literal["untested", "mixed"] = "untested") -> ContractResponse:
    """Integrity Contract status per property. All five start UNTESTED.

    Mock only: `?fixture=mixed` returns a post-run state with held/broken properties and counterexamples.
    """
    return serve(f"contract_{fixture}", ContractResponse, OWNER, trial_id=trial_id)

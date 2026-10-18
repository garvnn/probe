from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from backend.models import TestAttackerRequest, TestAttackerResult
from backend.routes._mode import serve
from backend.config import demo_mode
from engine.fake_data.stranger import frozen_hashes, report_path

router = APIRouter(prefix="/test-attacker", tags=["test-attacker"])
OWNER = "Shreyas"


@router.post("/eval", response_model=TestAttackerResult)
def test_attacker_eval(body: TestAttackerRequest) -> TestAttackerResult:
    """Run the test attacker (never seen during patching) against each check-suite version."""
    if demo_mode() == "mock":
        return serve("test_attacker", TestAttackerResult, OWNER)
    try:
        report = json.loads(report_path().read_text())
    except FileNotFoundError:
        raise HTTPException(404, "No measured Stranger report; run scripts/eval_stranger.py") from None
    if report.get("trial_id") != body.trial_id or body.attacker_id != "test":
        raise HTTPException(404, "No Stranger report for this trial/attacker")
    if report.get("frozen_sha256") != frozen_hashes() or report.get("_mock") is not False:
        raise HTTPException(409, "Stranger report is stale or lacks measured provenance")
    rows = [r for r in report["rows"] if r["suite_version"] in body.suite_versions]
    if {r["suite_version"] for r in rows} != set(body.suite_versions):
        raise HTTPException(404, "Requested suite version has not been evaluated")
    return TestAttackerResult.model_validate({**report, "rows": rows})

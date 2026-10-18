from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import demo_mode
from backend.mocks import load_mock
from backend.models import (
    BlindLeakResultModel,
    BlindLeakRunRequest,
    GuessCardResult,
    GuessCards,
    GuessScore,
    GuessScoreRequest,
    CheapestFixRequest,
    CheapestFixResult,
    PolicyRequest,
)
from backend.routes._mode import serve
from engine.blind_leak import cache
from engine.blind_leak.remedies import validate

router = APIRouter(prefix="/blind-leak", tags=["blind-leak"])
OWNER = "Ajay"


def _saved(kind: str) -> dict:
    """Cached mode: the newest saved Tell/Seal result (scripts/run_tell.py), never the fixture."""
    data = cache.latest(kind)
    if data is None:
        raise HTTPException(status_code=404, detail=f"no saved {kind} result; run python -m scripts.run_tell {kind}")
    return data


@router.post("/runs", response_model=BlindLeakResultModel)
def blind_leak_run(body: BlindLeakRunRequest) -> BlindLeakResultModel:
    """Run the blind-leak attack on one role's view (engine.blind_leak.result.run_blind)."""
    if demo_mode() == "cached":
        return BlindLeakResultModel.model_validate(_saved("tell"))
    return serve("blind_leak_run", BlindLeakResultModel, OWNER, trial_id=body.trial_id, view=body.view)


@router.post("/policy", response_model=BlindLeakResultModel)
def blind_leak_policy(body: PolicyRequest) -> BlindLeakResultModel:
    """Apply remedies, re-run, return accuracy + utility."""
    if demo_mode() == "cached":
        seal = _saved("seal")
        row = next((r for r in seal["results"] if r["combo"] == validate(list(body.remedies))), None)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no saved Seal row for {body.remedies}")
        return BlindLeakResultModel(mock=False, trial_id=seal["trial_id"], view=seal["view"], remedies=row["combo"], top_leaks=[],
                                    n_permutations=seal["n_permutations"], blind_holds=row["blind_restored"], **row)
    return serve("blind_leak_policy", BlindLeakResultModel, OWNER, trial_id=body.trial_id, view=body.view, remedies=body.remedies)


@router.post("/cheapest-fix", response_model=CheapestFixResult)
def blind_leak_cheapest_fix(body: CheapestFixRequest) -> CheapestFixResult:
    """All 16 remedy combinations + the recommended cheapest fix (engine.blind_leak.cheapest_fix.cheapest_fix)."""
    if demo_mode() == "cached":
        return CheapestFixResult.model_validate(_saved("seal"))
    return serve("blind_leak_cheapest_fix", CheapestFixResult, OWNER, trial_id=body.trial_id)


@router.get("/guess-cards", response_model=GuessCards)
def guess_cards(trial_id: str = "tr_2026_B") -> GuessCards:
    """Six coordinator-view patient cards for Guess Who. No labels."""
    return serve("guess_cards", GuessCards, OWNER, trial_id=trial_id)


@router.post("/guess-cards/score", response_model=GuessScore)
def score_guesses(body: GuessScoreRequest) -> GuessScore:
    """Score the judge's guesses; return Probe's guesses and the truth."""
    mode = demo_mode()
    if mode == "live":
        raise NotImplementedError(f"owner: {OWNER} ({mode} mode)")
    key = load_mock("guess_cards_key")
    assert isinstance(key, dict)
    cards = [
        GuessCardResult(card_id=c["card_id"], judge=body.guesses.get(c["card_id"]), probe=c["probe"], truth=c["truth"])
        for c in key["cards"]
    ]
    return GuessScore(
        mock=True,
        trial_id=body.trial_id,
        n=len(cards),
        judge_correct=sum(c.judge == c.truth for c in cards),
        probe_correct=sum(c.probe == c.truth for c in cards),
        cards=cards,
    )

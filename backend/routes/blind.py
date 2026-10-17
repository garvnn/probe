from __future__ import annotations

from fastapi import APIRouter

from backend.config import demo_mode
from backend.mocks import load_mock
from backend.models import (
    BlindResultModel,
    BlindRunRequest,
    GuessCardResult,
    GuessCards,
    GuessScore,
    GuessScoreRequest,
    MinimumFixRequest,
    MinimumFixResult,
    PolicyRequest,
)
from backend.routes._mode import serve

router = APIRouter(prefix="/blind", tags=["blind"])
OWNER = "Ajay"


@router.post("/runs", response_model=BlindResultModel)
def blind_run(body: BlindRunRequest) -> BlindResultModel:
    """Run the Blind Breaker on one role's view (engine.blind.result.run_blind)."""
    return serve("blind_run", BlindResultModel, OWNER, trial_id=body.trial_id, view=body.view)


@router.post("/policy", response_model=BlindResultModel)
def blind_policy(body: PolicyRequest) -> BlindResultModel:
    """Apply remedies, re-run, return accuracy + utility."""
    return serve("blind_policy", BlindResultModel, OWNER, trial_id=body.trial_id, view=body.view, remedies=body.remedies)


@router.post("/minimum-fix", response_model=MinimumFixResult)
def blind_minimum_fix(body: MinimumFixRequest) -> MinimumFixResult:
    """All 16 remedy combinations + the recommended cheapest fix (engine.blind.minimum_fix)."""
    return serve("blind_minimum_fix", MinimumFixResult, OWNER, trial_id=body.trial_id)


@router.get("/guess-cards", response_model=GuessCards)
def guess_cards(trial_id: str = "tr_2026_B") -> GuessCards:
    """Six coordinator-view patient cards for Guess Who. No labels."""
    return serve("guess_cards", GuessCards, OWNER, trial_id=trial_id)


@router.post("/guess-cards/score", response_model=GuessScore)
def score_guesses(body: GuessScoreRequest) -> GuessScore:
    """Score the judge's guesses; return Probe's guesses and the truth."""
    mode = demo_mode()
    if mode != "mock":
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

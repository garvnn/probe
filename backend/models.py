"""Pydantic request/response models for every route.

Every response model has a `_mock` field (python attribute `mock`). Fixtures set it to true so
no one mistakes a mock payload for a measured result.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["coordinator", "investigator", "pharmacist", "assessor"]
Arm = Literal["drug", "placebo"]
Remedy = Literal["unblinded_pharmacist", "sham_titration", "central_lab", "matched_kits"]


class Response(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mock: bool = Field(default=False, alias="_mock")


# ---------------------------------------------------------------- contract


class ContractStatus(str, Enum):
    untested = "untested"
    held = "held"
    broken = "broken"


class ContractPropertyName(str, Enum):
    """The five Integrity Contract properties, named as in the README table."""

    data_authenticity = "data_authenticity"
    treatment_confidentiality = "treatment_confidentiality"
    statistical_integrity = "statistical_integrity"
    safety_accessibility = "safety_accessibility"
    operational_utility = "operational_utility"


class ContractProperty(BaseModel):
    name: ContractPropertyName
    status: ContractStatus = ContractStatus.untested
    counterexample: str | None = None


class ContractResponse(Response):
    trial_id: str
    properties: list[ContractProperty]


# ---------------------------------------------------------------- trials


class TrialCreate(BaseModel):
    scenario: Literal["A", "B"]
    seed: int = 2026
    n_sites: int = 20
    patients_per_site: int = 40
    mechanisms: dict = Field(default_factory=dict)


class TrialSummary(Response):
    trial_id: str
    n_patients: int
    sites: int
    roles: list[Role]


class TrialDetail(Response):
    trial_id: str
    scenario: Literal["A", "B"]
    seed: int
    n_sites: int
    n_patients: int
    drug: str
    endpoint: str
    role_matrix: dict[Role, dict[str, bool]]
    """Role -> field group -> visible. Drives the "who sees what" panel."""


# ---------------------------------------------------------------- forger


class ForgerRunCreate(BaseModel):
    trial_id: str
    attacker_id: str = "A"
    detector_version: int = 0
    rounds: int = 8


class ForgerRun(Response):
    run_id: str
    trial_id: str
    attacker_id: str
    detector_version: int
    status: Literal["queued", "running", "done", "error"]


class RoundDamage(BaseModel):
    effect_real: float
    effect_with_fake: float
    p_with_fake: float


class RoundEvent(Response):
    """One SSE event per forger round."""

    round: int
    sandbox_id: str
    runtime_s: float
    ok: bool
    scores: dict[str, float] | None
    combined: float | None
    threshold: float
    escaped: bool
    damage: RoundDamage | None


# ---------------------------------------------------------------- detector / held-out


class HardenRequest(BaseModel):
    trial_id: str
    run_id: str
    detector_version: int = 0


class HardenResult(Response):
    new_version: int
    status: str
    """"accepted" or "rejected: <reason>"."""
    created_by: Literal["droid", "fallback"]
    check_name: str
    check_source: str
    caught: int
    n_escaped: int
    fp_before: float
    fp_after: float


class HeldoutRequest(BaseModel):
    trial_id: str
    attacker_id: str = "B"
    detector_versions: list[int] = Field(default_factory=lambda: [0])


class HeldoutRow(BaseModel):
    detector_version: int
    attacker_id: str
    attempted: int
    escaped: int
    evasion_rate: float
    ci95: tuple[float, float]
    """Wilson 95% interval."""
    fp_rate: float


class HeldoutResult(Response):
    attacker_id: str
    never_seen_during_hardening: bool
    rows: list[HeldoutRow]


# ---------------------------------------------------------------- blind


class BlindRunRequest(BaseModel):
    trial_id: str
    view: Role = "coordinator"


class PolicyRequest(BaseModel):
    trial_id: str
    view: Role = "assessor"
    remedies: list[Remedy] = Field(default_factory=list)


class Leak(BaseModel):
    field: str
    label: str
    importance: float


class BlindResultModel(Response):
    trial_id: str
    view: Role
    remedies: list[Remedy] = Field(default_factory=list)
    accuracy: float
    auc: float
    null_lo: float
    null_hi: float
    utility: float
    top_leaks: list[Leak]


class MinimumFixRequest(BaseModel):
    trial_id: str
    utility_floor: float = 0.90
    auc_ceiling: float = 0.55


class RemedyCombo(BaseModel):
    combo: list[Remedy]
    auc: float
    utility: float
    cost: float
    safety_ok: bool


class MinimumFixResult(Response):
    trial_id: str
    utility_floor: float
    auc_ceiling: float
    costs_are_assigned: bool = True
    recommended: RemedyCombo | None
    results: list[RemedyCombo]


class GuessCard(BaseModel):
    card_id: str
    visible: dict[str, str | int | float]
    """Coordinator-view fields only. Never the arm."""


class GuessCards(Response):
    trial_id: str
    cards: list[GuessCard]


class GuessScoreRequest(BaseModel):
    trial_id: str
    guesses: dict[str, Arm]
    """card_id -> the judge's guess."""


class GuessCardResult(BaseModel):
    card_id: str
    judge: Arm | None
    probe: Arm
    truth: Arm


class GuessScore(Response):
    trial_id: str
    n: int
    judge_correct: int
    probe_correct: int
    cards: list[GuessCardResult]


# ---------------------------------------------------------------- margin / report


class MarginRequest(BaseModel):
    trial_id: str
    detector_version: int = 0
    max_k: int = 6


class MarginPoint(BaseModel):
    k: int
    effect: float
    p: float


class MarginResult(Response):
    trial_id: str
    detector_version: int
    curve: list[MarginPoint]
    break_k: int | None


class Headline(BaseModel):
    label: str
    before: str
    after: str


class Report(Response):
    trial_id: str
    contract: list[ContractProperty]
    headlines: list[Headline]
    margin_v0: MarginResult
    margin_vN: MarginResult
    fixes: list[str]

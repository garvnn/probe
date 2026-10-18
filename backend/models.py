"""Pydantic request/response models for every route.

Every response model has a `_mock` field (python attribute `mock`). Fixtures set it to true so
no one mistakes a mock payload for a measured result.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.simulator.mechanisms import DEFAULT_MECHANISMS

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
    mechanisms: dict = Field(default_factory=lambda: dict(DEFAULT_MECHANISMS))
    """Leaks on by default; send {} for the control trial."""


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


# ---------------------------------------------------------------- fake data


class FakeDataRunCreate(BaseModel):
    trial_id: str
    attacker_id: str = "training"
    suite_version: int = 0
    rounds: int = 8


class FakeDataRun(Response):
    run_id: str
    trial_id: str
    attacker_id: str
    suite_version: int
    status: Literal["queued", "running", "done", "error"]


class RoundDamage(BaseModel):
    effect_real: float
    effect_with_fake: float
    p_with_fake: float
    p_real: float | None = None


class DiagnosticMeasure(BaseModel):
    measure: str
    your_site: float | None
    real_sites_typical: list[float | None]
    """[10th, 90th] percentile on real sites."""
    position: str
    """"below" | "above" | "within" | "not computable (...)"."""


class Diagnostic(BaseModel):
    """Why one check fired: what it measured on the fake site vs real sites (engine.fake_data.explain)."""

    check: str
    measures: list[DiagnosticMeasure]
    summary: str


class RoundEvent(Response):
    """One SSE event per fake-data round."""

    round: int
    sandbox_id: str
    runtime_s: float
    ok: bool
    scores: dict[str, float] | None
    combined: float | None
    threshold: float
    escaped: bool
    damage: RoundDamage | None
    code: str | None = None
    """The attacker's fake-site source for this round."""
    fired: list[str] = Field(default_factory=list)
    """Checks at or above the threshold (what the attacker was told)."""
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    error: str | None = None
    attacker_model: str | None = None
    attacker_s: float | None = None
    """Seconds the attacker took to write the code."""


class FakeDataRunDetail(Response):
    """Header of a saved fake-data run: who attacked what, with which check suite."""

    run_id: str
    trial_id: str
    fake_site_id: str | None
    attacker_id: str
    attacker_kind: str
    attacker_model: str
    attacker_seed: int | None
    suite_version: int
    threshold: float
    runner: str
    rounds_planned: int
    rounds_done: int
    input_tokens: int
    output_tokens: int
    label: str | None
    """Set on stand-in runs ("TEMPORARY ... Not a result.")."""


# ---------------------------------------------------------------- patch / test attacker


class PatchRequest(BaseModel):
    trial_id: str
    run_id: str
    suite_version: int = 0


class PatchResult(Response):
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


class TestAttackerRequest(BaseModel):
    trial_id: str
    attacker_id: str = "test"
    suite_versions: list[int] = Field(default_factory=lambda: [0])


class TestAttackerRow(BaseModel):
    suite_version: int
    attacker_id: str
    attempted: int
    escaped: int
    evasion_rate: float
    ci95: tuple[float, float]
    """Wilson 95% interval."""
    fp_rate: float


class TestAttackerResult(Response):
    attacker_id: str
    never_seen_during_patching: bool
    rows: list[TestAttackerRow]


# ---------------------------------------------------------------- blind


class BlindLeakRunRequest(BaseModel):
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
    group: str | None = None
    drop_auc: float | None = None


class BlindLeakResultModel(Response):
    trial_id: str
    view: Role
    remedies: list[Remedy] = Field(default_factory=list)
    accuracy: float
    auc: float
    null_lo: float
    null_hi: float
    utility: float
    top_leaks: list[Leak]
    # Optional detail from real Tell runs (absent in fixtures).
    scenario: str | None = None
    mechanisms: str | None = None
    p_value: float | None = None
    n_permutations: int | None = None
    null_accuracy: list[float] | None = None
    blind_holds: bool | None = None
    control: BlindLeakResultModel | None = None
    """Same trial design with every leak mechanism off; must be at chance."""


class CheapestFixRequest(BaseModel):
    trial_id: str
    utility_floor: float = 0.90
    auc_ceiling: float = 0.55


class RemedyCombo(BaseModel):
    combo: list[Remedy]
    auc: float
    utility: float
    cost: float
    safety_ok: bool
    accuracy: float | None = None
    p_value: float | None = None
    null_lo: float | None = None
    null_hi: float | None = None
    blind_restored: bool | None = None
    acceptable: bool | None = None


class CheapestFixResult(Response):
    trial_id: str
    utility_floor: float
    auc_ceiling: float
    costs_are_assigned: bool = True
    recommended: RemedyCombo | None
    results: list[RemedyCombo]
    view: Role | None = None
    acceptance_rule: str | None = None
    n_permutations: int | None = None
    best_partial: RemedyCombo | None = None
    """Set only when no combo is acceptable."""


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


# ---------------------------------------------------------------- breaking point / report


class BreakingPointRequest(BaseModel):
    trial_id: str
    suite_version: int = 0
    max_k: int = 6


class BreakingPointRow(BaseModel):
    k: int
    effect: float
    p: float


class BreakingPointResult(Response):
    trial_id: str
    suite_version: int
    curve: list[BreakingPointRow]
    break_k: int | None


class Headline(BaseModel):
    label: str
    before: str
    after: str


class Report(Response):
    trial_id: str
    contract: list[ContractProperty]
    headlines: list[Headline]
    breaking_point_v0: BreakingPointResult
    breaking_point_vN: BreakingPointResult
    fixes: list[str]

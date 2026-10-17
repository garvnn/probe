"""Acceptance gate for new fraud checks. Owner: Garv.

A new check ships only if, at the frozen v0 threshold:
  1. false alarms on held-out real sites rise by at most FP_TOLERANCE (1 point), and
  2. it catches a clear majority of held-out fakes that escaped v0: the 95% Wilson lower bound on
     the catch rate is above 50%, with at least MIN_HELDOUT_ESCAPES escapes to judge from.
Held-out fakes come only from runs the check was not trained on. Too few escapes is reported as
"insufficient", never as a pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from engine.fraud_checks.base import SiteCheck, SiteData
from engine.fraud_checks.suite import CheckSuite

OWNER = "Garv"

FP_TOLERANCE = 0.01
MIN_HELDOUT_ESCAPES = 10
"""Below this many held-out v0 escapes, the gate can't mean anything: report insufficient."""
CLEAR_MAJORITY = 0.5
"""The Wilson 95% lower bound on the catch rate must exceed this."""


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval for k successes in n trials ((0, 1) when n = 0)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return float(max(0.0, center - half)), float(min(1.0, center + half))


@dataclass
class GateResult:
    """Everything the gate decided on, with counts."""

    accepted: bool
    status: str
    """"accepted", "rejected: <reason>", or "insufficient: <reason>"."""
    threshold: float
    n_real: int
    flagged_before: int
    flagged_after: int
    n_heldout_fakes: int
    n_escaped: int
    """Held-out fakes that escaped v0."""
    caught: int
    """Of those, how many the candidate flags."""
    reasons: list[str] = field(default_factory=list)

    @property
    def fp_before(self) -> float:
        return self.flagged_before / self.n_real if self.n_real else 0.0

    @property
    def fp_after(self) -> float:
        return self.flagged_after / self.n_real if self.n_real else 0.0

    @property
    def caught_ci(self) -> tuple[float, float]:
        return wilson(self.caught, self.n_escaped)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(fp_before=round(self.fp_before, 4), fp_after=round(self.fp_after, 4), caught_ci=[round(x, 3) for x in self.caught_ci])
        return d


def evaluate_gate(
    threshold: float,
    real_before: np.ndarray,
    real_after: np.ndarray,
    fake_before: np.ndarray,
    fake_after: np.ndarray,
    fp_tolerance: float = FP_TOLERANCE,
    min_escapes: int = MIN_HELDOUT_ESCAPES,
) -> GateResult:
    """The gate on precomputed combined scores: held-out real sites and held-out fakes, under the
    current suite (before) and the candidate (after), all at `threshold`."""
    real_before, real_after = np.asarray(real_before), np.asarray(real_after)
    fake_before, fake_after = np.asarray(fake_before), np.asarray(fake_after)
    escaped = fake_before < threshold
    result = GateResult(
        accepted=False,
        status="",
        threshold=threshold,
        n_real=len(real_before),
        flagged_before=int((real_before >= threshold).sum()),
        flagged_after=int((real_after >= threshold).sum()),
        n_heldout_fakes=len(fake_before),
        n_escaped=int(escaped.sum()),
        caught=int((fake_after[escaped] >= threshold).sum()),
    )
    rise = result.fp_after - result.fp_before
    lo, _ = result.caught_ci
    if rise > fp_tolerance + 1e-12:
        result.reasons.append(f"false alarms on held-out real sites rose {rise * 100:.1f} points (limit {fp_tolerance * 100:.0f})")
    if result.n_escaped < min_escapes:
        result.status = f"insufficient: {result.n_escaped} held-out fakes escaped v0; the gate needs at least {min_escapes}"
        result.reasons.append(result.status[len("insufficient: "):])
        return result
    if lo <= CLEAR_MAJORITY:
        result.reasons.append(f"caught {result.caught}/{result.n_escaped} held-out escapes; 95% lower bound {lo:.0%} is not above {CLEAR_MAJORITY:.0%}")
    result.accepted = not result.reasons
    result.status = "accepted" if result.accepted else "rejected: " + "; ".join(result.reasons)
    return result


def accept_check(
    suite: CheckSuite,
    new_check: SiteCheck,
    fake_holdout: list[tuple[SiteData, list[SiteData]]],
    real_holdout: list[tuple[SiteData, list[SiteData]]],
    fp_tolerance: float = FP_TOLERANCE,
) -> tuple[CheckSuite, str]:
    """Gate any SiteCheck (Droid-written or learned) against held-out (site, reference) pairs.

    Returns (candidate, "accepted") or (suite, "rejected: ..." / "insufficient: ...").
    """
    candidate = suite.with_check(new_check)

    def combined(s: CheckSuite, pairs) -> np.ndarray:
        return np.array([s.score_site(site, ref).combined for site, ref in pairs])

    result = evaluate_gate(
        suite.threshold,
        combined(suite, real_holdout),
        combined(candidate, real_holdout),
        combined(suite, fake_holdout),
        combined(candidate, fake_holdout),
        fp_tolerance,
    )
    return (candidate if result.accepted else suite), result.status

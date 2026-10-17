"""The CheckSuite: a versioned battery of SiteChecks with a frozen threshold. Owner: Garv."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from engine.fraud_checks.base import SiteCheck, SiteData, clip_score, others

OWNER = "Garv"

FROZEN_DIR = Path(__file__).parent / "frozen"
"""Frozen suite versions (v0.json is the calibrated baseline). Written by engine.fraud_checks.calibrate."""


@dataclass
class SiteScores:
    """Scores for one site.

    Attributes:
        per_check: Check name -> score.
        combined: Combined site risk score, compared against the check-suite threshold. It is the
            highest per-check score, so a site is flagged exactly when at least one check fired.
    """

    per_check: dict[str, float]
    combined: float

    def fired(self, threshold: float) -> list[str]:
        """Names of the checks whose score crossed `threshold`. This is what the attacker sees."""
        return [name for name, score in self.per_check.items() if score >= threshold]


@dataclass
class CheckSuite:
    """A check-suite version.

    Attributes:
        checks: The check battery.
        threshold: Combined-score cutoff, calibrated so ≤5% of real sites are flagged,
            then frozen before any attack runs. A site is flagged when combined >= threshold
            (so it escaped when combined < threshold).
        version: 0 for the baseline battery; incremented by each accepted check.
    """

    checks: list[SiteCheck]
    threshold: float
    version: int = 0
    meta: dict = field(default_factory=dict, compare=False)
    """Calibration details from the frozen file (seeds, budget, measured false-alarm rate)."""
    name: str = "sentinel"
    """Shown in saved runs and the UI next to `version`."""

    def score_site(self, site: SiteData, reference: list[SiteData]) -> SiteScores:
        """Run every check on `site` and combine the scores. `site` is never compared with itself."""
        ref = others(site, reference)
        per_check = {check.name: clip_score(check.score(site, ref)) for check in self.checks}
        return SiteScores(per_check=per_check, combined=max(per_check.values()))

    def flags(self, site: SiteData, reference: list[SiteData]) -> bool:
        """True if `site` is flagged against `reference`."""
        return self.score_site(site, reference).combined >= self.threshold

    def false_alarm_rate(self, real_sites: list[SiteData]) -> float:
        """Fraction of real (non-fake) sites flagged at the current threshold, each scored against the others."""
        if not real_sites:
            return 0.0
        return sum(self.flags(site, real_sites) for site in real_sites) / len(real_sites)

    def with_check(self, check: SiteCheck) -> CheckSuite:
        """Return a new CheckSuite (version + 1) with `check` added. Does not mutate self.

        The threshold stays frozen; adding a check can only flag more sites, which is why the
        patch gate re-measures false alarms.
        """
        return CheckSuite(checks=[*self.checks, check], threshold=self.threshold, version=self.version + 1, meta={"parent": self.version}, name=self.name)


def check_registry() -> dict[str, type]:
    """Check name -> class, for every built-in check."""
    from engine.fraud_checks.checks_core import CORE_CHECKS
    from engine.fraud_checks.checks_rates import RATE_CHECKS

    return {cls.name: cls for cls in (*CORE_CHECKS, *RATE_CHECKS)}


def load_suite(version: int = 0, frozen_dir: Path | None = None) -> CheckSuite:
    """Load a frozen suite version (v0 = the calibrated baseline battery, v1 = v0 + the learned check).

    Checks with saved parameters (the learned check) are rebuilt from the file's `check_params`.
    """
    path = (frozen_dir or FROZEN_DIR) / f"v{version}.json"
    if not path.exists():
        how = "python -m engine.fraud_checks.calibrate" if version == 0 else "scripts/run_patch.py (only freezes if the gate accepts)"
        raise FileNotFoundError(f"{path} missing; created by {how}")
    data = json.loads(path.read_text())
    from engine.patch.fallback_check import FallbackClassifierCheck

    registry = {**check_registry(), FallbackClassifierCheck.name: FallbackClassifierCheck}
    params = data.get("check_params", {})
    checks = [registry[name].from_params(params[name]) if name in params else registry[name]() for name in data["checks"]]
    return CheckSuite(checks=checks, threshold=data["threshold"], version=data["version"], meta=data)

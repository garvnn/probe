"""The Detector: a versioned battery of SiteChecks with a frozen threshold. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass

from engine.detector.base import SiteCheck, SiteData

OWNER = "Garv"


@dataclass
class SiteScores:
    """Scores for one site.

    Attributes:
        per_check: Check name -> score.
        combined: Combined site risk score, compared against the detector threshold.
    """

    per_check: dict[str, float]
    combined: float

    def fired(self, threshold: float) -> list[str]:
        """Names of the checks whose score crossed `threshold`. This is what the attacker sees."""
        raise NotImplementedError(f"owner: {OWNER}")


@dataclass
class Detector:
    """A detector version.

    Attributes:
        checks: The check battery.
        threshold: Combined-score cutoff, calibrated so ≤5% of real sites are flagged,
            then frozen before any attack runs.
        version: 0 for the baseline battery; incremented by each accepted check.
    """

    checks: list[SiteCheck]
    threshold: float
    version: int = 0

    def score_site(self, site: SiteData, reference: list[SiteData]) -> SiteScores:
        """Run every check on `site` and combine the scores."""
        raise NotImplementedError(f"owner: {OWNER}")

    def false_alarm_rate(self, real_sites: list[SiteData]) -> float:
        """Fraction of real (non-fake) sites flagged at the current threshold."""
        raise NotImplementedError(f"owner: {OWNER}")

    def with_check(self, check: SiteCheck) -> Detector:
        """Return a new Detector (version + 1) with `check` added. Does not mutate self."""
        raise NotImplementedError(f"owner: {OWNER}")

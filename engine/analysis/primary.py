"""Primary analysis: ANCOVA on week-24 HbA1c change. Owner: Garv."""

from __future__ import annotations

from engine.fraud_checks.base import SiteData
from engine.simulator.trial import Trial

OWNER = "Garv"


def primary_analysis(trial: Trial, extra_sites: list[SiteData] | None = None) -> tuple[float, float]:
    """ANCOVA: week-24 HbA1c change ~ arm + baseline HbA1c + site (as factor).

    `extra_sites` are fake sites to include alongside the real ones. Returns (effect_estimate, p_value).
    """
    raise NotImplementedError(f"owner: {OWNER}")

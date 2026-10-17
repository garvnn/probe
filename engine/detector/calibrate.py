"""Threshold calibration against the false-alarm budget. Owner: Garv."""

from __future__ import annotations

from engine.detector.base import SiteCheck, SiteData

OWNER = "Garv"

FALSE_ALARM_BUDGET = 0.05
"""At most 5% of real sites may be flagged. Fixed before any attack runs."""


def calibrate_threshold(checks: list[SiteCheck], real_sites: list[SiteData], budget: float = FALSE_ALARM_BUDGET) -> float:
    """Return the combined-score threshold that flags at most `budget` of `real_sites`."""
    raise NotImplementedError(f"owner: {OWNER}")

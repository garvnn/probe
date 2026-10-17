"""Acceptance gate for new detector checks. Owner: Shreyas."""

from __future__ import annotations

from engine.detector.base import SiteCheck, SiteData
from engine.detector.detector import Detector

OWNER = "Shreyas"


def accept_check(
    detector: Detector,
    new_check: SiteCheck,
    escaped_fakes: list[SiteData],
    real_holdout: list[SiteData],
    fp_tolerance: float = 0.01,
) -> tuple[Detector, str]:
    """Accept `new_check` only if false alarms on held-out real sites rise by at most `fp_tolerance`
    and the candidate catches more than half of `escaped_fakes`.

    Returns (candidate, "accepted") or (detector, "rejected: <reason>").
    """
    raise NotImplementedError(f"owner: {OWNER}")

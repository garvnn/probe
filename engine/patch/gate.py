"""Acceptance gate for new fraud checks. Owner: Shreyas."""

from __future__ import annotations

from engine.fraud_checks.base import SiteCheck, SiteData
from engine.fraud_checks.suite import CheckSuite

OWNER = "Shreyas"


def accept_check(
    suite: CheckSuite,
    new_check: SiteCheck,
    escaped_fakes: list[SiteData],
    real_holdout: list[SiteData],
    fp_tolerance: float = 0.01,
) -> tuple[CheckSuite, str]:
    """Accept `new_check` only if false alarms on holdout real sites rise by at most `fp_tolerance`
    and the candidate catches more than half of `escaped_fakes`.

    Returns (candidate, "accepted") or (suite, "rejected: <reason>").
    """
    raise NotImplementedError(f"owner: {OWNER}")

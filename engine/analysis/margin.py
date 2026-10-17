"""Integrity margin: how many undetected fake sites until the conclusion flips. Owner: Garv.

Reuses fakes that already escaped; no new LLM calls. Measures the trial's fragility inside the
simulator; it is not guidance for faking real trials.
"""

from __future__ import annotations

from engine.detector.base import SiteData
from engine.generator.trial import Trial

OWNER = "Garv"


def integrity_margin(trial: Trial, escaped_fakes: list[SiteData], max_k: int = 6) -> tuple[list[dict], int | None]:
    """Run the primary analysis with 0, 1, ..., max_k escaped fakes included.

    Returns (curve, break_k): curve entries are {"k", "effect", "p"}; break_k is the first k where
    the conclusion flips (p < 0.05 in Scenario B), or None if it never does.
    """
    raise NotImplementedError(f"owner: {OWNER}")

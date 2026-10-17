"""Damage: how far undetected fakes move the trial's result. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass

from engine.fraud_checks.base import SiteData
from engine.simulator.trial import Trial

OWNER = "Garv"


@dataclass
class Damage:
    """Effect estimate and p-value, real trial vs real + fakes."""

    effect_real: float
    p_real: float
    effect_with_fake: float
    p_with_fake: float


def effect_shift(trial: Trial, fake_sites: list[SiteData]) -> Damage:
    """Re-run the primary analysis with `fake_sites` included and compare against the real trial."""
    raise NotImplementedError(f"owner: {OWNER}")

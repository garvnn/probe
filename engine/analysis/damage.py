"""Damage: how far undetected fakes move the trial's result. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass

from engine.analysis.primary import primary_result
from engine.fraud_checks.base import SiteData
from engine.simulator.trial import Trial

OWNER = "Garv"


@dataclass
class Damage:
    """Effect estimate and p-value, real trial vs real + fakes.

    `fake_patients_analyzed` is how many fake patients entered the analysis (each needs an arm from the
    attacker's ground_truth table and a Week 24 central HbA1c). 0 means the fakes couldn't move the result.
    """

    effect_real: float
    p_real: float
    effect_with_fake: float
    p_with_fake: float
    fake_patients_analyzed: int = 0


def effect_shift(trial: Trial, fake_sites: list[SiteData]) -> Damage:
    """Re-run the primary analysis with `fake_sites` included and compare against the real trial."""
    real = primary_result(trial)
    with_fake = primary_result(trial, fake_sites)
    return Damage(
        effect_real=real.effect,
        p_real=real.p,
        effect_with_fake=with_fake.effect,
        p_with_fake=with_fake.p,
        fake_patients_analyzed=with_fake.n_fake,
    )

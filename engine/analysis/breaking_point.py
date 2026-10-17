"""Breaking point: how many undetected fake sites until the conclusion flips. Owner: Garv.

Reuses fakes that already escaped; no new LLM calls. Measures the trial's fragility inside the
simulator; it is not guidance for faking real trials.
"""

from __future__ import annotations

from engine.analysis.primary import primary_result
from engine.fraud_checks.base import SiteData
from engine.simulator.trial import Trial

OWNER = "Garv"

ALPHA = 0.05


def concludes_drug_works(effect: float, p: float) -> bool:
    """The trial's conclusion: the drug lowered HbA1c more than placebo, significant at ALPHA."""
    return p < ALPHA and effect < 0


def breaking_point(trial: Trial, escaped_fakes: list[SiteData], max_k: int = 6) -> tuple[list[dict], int | None]:
    """Run the primary analysis with 0, 1, ..., max_k escaped fakes included.

    Returns (curve, break_k): curve entries are {"k", "effect", "p"}; break_k is the first k where
    the conclusion flips (p < 0.05 in Scenario B), or None if it never does.

    "Flips" means concludes_drug_works() differs from k = 0: in Scenario B (a useless drug) that is the
    first k where it looks like it works; in Scenario A, the first k where a working drug stops looking
    like it does. Fakes are added in the order given.
    """
    curve = []
    for k in range(min(max_k, len(escaped_fakes)) + 1):
        result = primary_result(trial, escaped_fakes[:k])
        curve.append({"k": k, "effect": result.effect, "p": result.p})
    base = concludes_drug_works(curve[0]["effect"], curve[0]["p"])
    break_k = next((c["k"] for c in curve[1:] if concludes_drug_works(c["effect"], c["p"]) != base), None)
    return curve, break_k

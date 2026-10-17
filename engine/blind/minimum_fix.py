"""Brute-force search for the cheapest remedy set that restores the blind. Owner: Ajay."""

from __future__ import annotations

OWNER = "Ajay"


def minimum_fix(
    trial_id: str,
    remedies: list[str],
    utility_floor: float = 0.90,
    auc_ceiling: float = 0.55,
) -> tuple[dict | None, list[dict]]:
    """Try every combination of `remedies` (16 for 4 remedies) on the assessor view.

    Each result: {"combo", "auc", "utility", "cost", "safety_ok"}. Feasible = auc <= auc_ceiling,
    utility >= utility_floor, safety_ok. Returns (cheapest feasible or None, all results for the
    Pareto chart). The floor and ceiling are our chosen targets; label them in the UI.
    """
    raise NotImplementedError(f"owner: {OWNER}")

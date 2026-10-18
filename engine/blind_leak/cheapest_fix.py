"""Exhaustive Seal search on the permitted assessor export. Owner: Ajay."""
from __future__ import annotations

from itertools import combinations
import math

from engine.blind_leak.remedies import REMEDIES, REMEDY_COST
from engine.blind_leak.result import run_blind
from engine.blind_leak.utility import safety_accessible, utility

OWNER = "Ajay"
# REMEDY_COST is assigned by us, not an empirical monetary estimate. The UI must
# label these costs as assigned (the API sets costs_are_assigned=True).
# Reuse the existing four-remedy registry and assigned costs to avoid divergent prices.


def export_view(trial_id: str, role: str, remedies: list[str]):
    """The documented export_view API is the only simulator-facing boundary.

    No simulator implementation, schema code, or generation internals are inspected.
    """
    from engine.simulator.views import export_view as public_export_view

    return public_export_view(trial_id, role, remedies=remedies)


def cheapest_fix(
    trial_id: str,
    utility_floor: float = 0.90,
    auc_ceiling: float = 0.55,
) -> tuple[dict | None, list[dict]]:
    """Evaluate every subset; return the cheapest feasible row and all Pareto rows.

    Utility is the declared task model. Costs are assigned. AUC is grouped-CV AUC
    from run_blind; the search skips permutation-null refits and requests no
    reported attribution because neither affects that AUC. No permutation significance claim is made here.
    Equal-cost ties prefer fewer remedies, then the canonical registry order.
    """
    if not (0 <= utility_floor <= 1 and 0 <= auc_ceiling <= 1):
        raise ValueError("utility_floor and auc_ceiling must be between 0 and 1")
    rows = []
    for size in range(len(REMEDIES) + 1):
        for subset in combinations(REMEDIES, size):
            combo = list(subset)
            retained = utility(combo)
            result = run_blind(export_view(trial_id, "assessor", remedies=combo), trial_id,
                               n_permutations=0, top=0, utility=retained)
            rows.append({"combo": combo, "auc": float(result.auc), "utility": retained,
                         "cost": float(sum(REMEDY_COST[r] for r in combo)),
                         "safety_ok": safety_accessible(combo)})
    feasible = [r for r in rows if math.isfinite(r["auc"]) and r["auc"] <= auc_ceiling
                and r["utility"] >= utility_floor and r["safety_ok"]]
    best = min(feasible, key=lambda r: (r["cost"], len(r["combo"]))) if feasible else None
    return best, rows

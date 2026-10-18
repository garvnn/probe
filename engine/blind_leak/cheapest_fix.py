"""Brute-force search for the cheapest remedy set that restores the blind. Owner: Ajay.

Every subset of the remedies (16 for 4) is applied to the view, Tell is rerun (grouped CV plus the
permutation null), and utility is computed. A combo is ACCEPTABLE when utility >= utility_floor, safety
is preserved, and the blind is restored: permutation p >= 0.05 and accuracy inside the null's 95% band.
The cheapest acceptable combo wins; ties go to lower accuracy. Costs are ASSIGNED, not real-world.
"""

from __future__ import annotations

from itertools import combinations
from typing import Callable

import numpy as np
import pandas as pd

from engine.blind_leak.features import build_features
from engine.blind_leak.permutation import DEFAULT_N, run_permutation
from engine.blind_leak.remedies import REMEDIES, cost, validate
from engine.blind_leak.result import align
from engine.blind_leak.utility import safety_accessible, utility

OWNER = "Ajay"

ALPHA = 0.05
ACCEPTANCE_RULE = (
    "utility >= {floor:.2f}, safety preserved, permutation p >= 0.05, "
    "and accuracy inside the permutation null's 95% band"
)


def all_combos(remedies: list[str] = REMEDIES) -> list[list[str]]:
    remedies = validate(remedies)
    return [list(c) for k in range(len(remedies) + 1) for c in combinations(remedies, k)]


def evaluate_combos(
    get_view: Callable[[list[str]], pd.DataFrame],
    labels: pd.Series,
    remedies: list[str] = REMEDIES,
    utility_floor: float = 0.90,
    n_permutations: int = DEFAULT_N,
    seed: int = 0,
    progress: Callable[[int, list[str], dict], None] | None = None,
) -> tuple[dict | None, list[dict]]:
    """Run Tell on `get_view(combo)` for every combo. Returns (recommended or None, all rows)."""
    rows = []
    for i, combo in enumerate(all_combos(remedies)):
        X, y, groups = align(build_features(get_view(combo)), labels)
        r = run_permutation(X, y, groups, n=n_permutations, seed=seed)
        u = utility(combo)
        safe = safety_accessible(combo)
        restored = r.p_value >= ALPHA and r.accuracy_in_null
        row = {
            "combo": combo,
            "accuracy": r.observed.accuracy,
            "auc": r.observed.auc,
            "null_lo": r.null_lo,
            "null_hi": r.null_hi,
            "null_auc_hi": float(np.percentile(r.null_auc, 97.5)) if r.n else float("nan"),
            "p_value": r.p_value,
            "utility": u,
            "cost": cost(combo),
            "safety_ok": safe,
            "blind_restored": restored,
            "acceptable": restored and safe and u >= utility_floor,
            "n_features": X.shape[1],
        }
        rows.append(row)
        if progress:
            progress(i, combo, row)
    return pick(rows), rows


def pick(rows: list[dict]) -> dict | None:
    ok = [r for r in rows if r["acceptable"]]
    return min(ok, key=lambda r: (r["cost"], r["accuracy"])) if ok else None


def best_partial(rows: list[dict]) -> dict:
    """When nothing is acceptable: the cheapest safe combo that restores the blind (it fails only on
    utility), ties to lower accuracy. If none restores it, the safe combo with the lowest accuracy."""
    restored = [r for r in rows if r["safety_ok"] and r["blind_restored"]]
    if restored:
        return min(restored, key=lambda r: (r["cost"], r["accuracy"]))
    return min([r for r in rows if r["safety_ok"]] or rows, key=lambda r: (r["accuracy"], r["cost"]))


def cheapest_fix(
    trial_id: str,
    remedies: list[str] = REMEDIES,
    utility_floor: float = 0.90,
    role: str = "coordinator",
    n_permutations: int = DEFAULT_N,
    seed: int = 0,
) -> tuple[dict | None, list[dict]]:
    """Real-data entry point: views come from export_view(trial_id, role, remedies=combo)."""
    from engine.simulator.views import export_view
    from evals.scoring import arm_labels

    labels = arm_labels(trial_id)
    return evaluate_combos(lambda c: export_view(trial_id, role, remedies=c), labels, remedies,
                           utility_floor, n_permutations, seed)

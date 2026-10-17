"""BlindResult and the run_blind entry point. Owner: Ajay."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

OWNER = "Ajay"


@dataclass
class BlindResult:
    """Outcome of one Blind Breaker run on one view.

    Attributes:
        accuracy: Arm-prediction accuracy, cross-validated grouped by site.
        auc: ROC AUC, same CV.
        null_lo: Lower edge of the permutation-null band (shuffled labels).
        null_hi: Upper edge of the permutation-null band.
        utility: Operational utility retained by the remedies that produced this view (1.0 if none).
        top_leaks: Ranked leaking fields, e.g. [{"field": "unscheduled_visits", "label": "extra unscheduled visits", "importance": ...}].
    """

    accuracy: float
    auc: float
    null_lo: float
    null_hi: float
    utility: float
    top_leaks: list[dict]


def run_blind(view_df: pd.DataFrame, trial_id: str) -> BlindResult:
    """Featurize, classify, permutation-test, and attribute. Ground truth is joined only inside scoring."""
    raise NotImplementedError(f"owner: {OWNER}")

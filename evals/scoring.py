"""Labels for scoring the blind-leak attack. Owner: Ajay.

The only bridge from ground truth into Tell. run_blind calls this after features are built, and the
labels are used only as the classifier's target, never as a feature.
"""

from __future__ import annotations

import pandas as pd

OWNER = "Ajay"


def arm_labels(trial_id: str) -> pd.Series:
    """drug | placebo per patient_id, from evals.ground_truth."""
    from evals.ground_truth import ground_truth

    return ground_truth(trial_id)

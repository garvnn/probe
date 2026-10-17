"""Arm classifier with site-grouped cross-validation. Owner: Ajay.

Import lightgbm inside functions, not at module level (it needs libomp on macOS).
"""

from __future__ import annotations

import pandas as pd

OWNER = "Ajay"


def grouped_cv(X: pd.DataFrame, y: pd.Series, groups: pd.Series, n_splits: int = 5) -> tuple[float, float]:
    """Return (accuracy, auc), split by site so the model can't memorize a site."""
    raise NotImplementedError(f"owner: {OWNER}")

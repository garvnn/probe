"""Permutation null for arm-prediction accuracy. Owner: Ajay."""

from __future__ import annotations

import pandas as pd

OWNER = "Ajay"


def permutation_test(X: pd.DataFrame, y: pd.Series, groups: pd.Series, n: int = 200) -> tuple[float, float, float]:
    """Shuffle labels `n` times. Return (null_lo, null_hi, p_value) for the observed accuracy."""
    raise NotImplementedError(f"owner: {OWNER}")

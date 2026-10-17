"""Leak localization: SHAP + drop-column delta. Owner: Ajay."""

from __future__ import annotations

import pandas as pd

OWNER = "Ajay"


def rank_leaks(X: pd.DataFrame, y: pd.Series, groups: pd.Series) -> list[dict]:
    """Rank fields by how much they reveal the arm. Each entry carries a plain-English label for the UI."""
    raise NotImplementedError(f"owner: {OWNER}")

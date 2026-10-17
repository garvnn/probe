"""Small clinical helpers shared by the trial builder and the leak mechanisms. Owner: Garv."""

from __future__ import annotations

import numpy as np
import pandas as pd

SEVERITY = (("mild", 0.7), ("moderate", 0.25), ("severe", 0.05))


def eag(hba1c: np.ndarray | float) -> np.ndarray | float:
    """Estimated average glucose (mg/dL) from HbA1c (%), ADAG formula (Nathan et al. 2008)."""
    return 28.7 * hba1c - 46.7


def weekday(date: pd.Timestamp, rng: np.random.Generator) -> pd.Timestamp:
    """Most visits that would land on a weekend get moved to the nearest weekday."""
    if date.weekday() >= 5 and rng.random() < 0.95:
        return date + pd.Timedelta(days=-1 if date.weekday() == 5 else 1)
    return date


def severity(rng: np.random.Generator) -> str:
    names, probs = zip(*SEVERITY)
    return str(rng.choice(names, p=probs))

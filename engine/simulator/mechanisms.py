"""Documented leak mechanisms that leave operational traces. Owner: Garv.

Each mechanism must have a row in docs/assumptions.md (strength param, default, rationale, source).
No invented correlations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

OWNER = "Garv"


def apply_nausea(tables: dict[str, pd.DataFrame], arm: pd.Series, rr: float, rng: np.random.Generator) -> None:
    """Nausea on drug -> unscheduled visits, antiemetic conmeds, AE log entries. Mutates `tables`."""
    raise NotImplementedError(f"owner: {OWNER}")


def apply_titration(tables: dict[str, pd.DataFrame], arm: pd.Series, rng: np.random.Generator) -> None:
    """Dose titration on drug (wk 4, 8) -> pharmacy dispensing events. Mutates `tables`."""
    raise NotImplementedError(f"owner: {OWNER}")


def apply_local_glucose(tables: dict[str, pd.DataFrame], arm: pd.Series, rng: np.random.Generator) -> None:
    """Drug lowers glucose -> local fingerstick values differ. Mutates `tables`."""
    raise NotImplementedError(f"owner: {OWNER}")


def apply_cold_chain(tables: dict[str, pd.DataFrame], arm: pd.Series, rng: np.random.Generator) -> None:
    """Cold-chain drug -> kit storage / temperature log entries. Mutates `tables`."""
    raise NotImplementedError(f"owner: {OWNER}")

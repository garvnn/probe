"""Locked ground truth. Owner: Garv.

Only evals and scoring code may import this. Never import it from engine.blind, engine.forger,
engine.generator.views, or backend routes.
"""

from __future__ import annotations

import pandas as pd

OWNER = "Garv"


def ground_truth(trial_id: str) -> pd.Series:
    """Arm per patient ("drug" | "placebo"), indexed by patient_id."""
    raise NotImplementedError(f"owner: {OWNER}")

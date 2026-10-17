"""Locked ground truth. Owner: Garv.

Only evals and scoring code may import this. Never import it from engine.blind_leak, engine.fake_data,
engine.simulator.views, or backend routes.
"""

from __future__ import annotations

import pandas as pd

from engine.simulator import store

OWNER = "Garv"


def ground_truth(trial_id: str) -> pd.Series:
    """Arm per patient ("drug" | "placebo"), indexed by patient_id."""
    gt = store.load_ground_truth(trial_id)
    return pd.Series(gt["arm"].to_numpy(), index=pd.Index(gt["patient_id"], name="patient_id"), name="arm")

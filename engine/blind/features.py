"""Patient-level features from a role's view. Owner: Ajay."""

from __future__ import annotations

import pandas as pd

OWNER = "Ajay"


def build_features(view_df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient: unscheduled visit count, days between visits, conmed classes, AE counts by
    category, dispensing events, kit returns, local glucose trend, lab draw times. Indexed by patient_id;
    keeps site_id for grouped CV."""
    raise NotImplementedError(f"owner: {OWNER}")

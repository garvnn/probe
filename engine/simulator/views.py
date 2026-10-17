"""Role-filtered exports of a trial. Owner: Garv.

This is the only way the blind-leak attack sees trial data (bias firewall).
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

OWNER = "Garv"

Role = Literal["coordinator", "investigator", "pharmacist", "assessor"]


def export_view(trial_id: str, role: Role, remedies: list[str] = []) -> pd.DataFrame:  # noqa: B006
    """Return the patient-level data `role` is allowed to see, after applying `remedies`.

    Never includes the arm column, or anything derived from ground truth. Remedy names are
    those in `engine.blind_leak.remedies.REMEDIES`; each one removes or normalizes the fields it
    covers (e.g. "central_lab" removes local glucose values).
    """
    raise NotImplementedError(f"owner: {OWNER}")

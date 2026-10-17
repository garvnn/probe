"""Trial config, the Trial container, and generate/load entry points. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

OWNER = "Garv"

TABLES = (
    "patients",
    "sites",
    "visits",
    "labs",
    "vitals",
    "adverse_events",
    "conmeds",
    "dispensing",
)
"""Table names a Trial carries. `ground_truth` is deliberately not one of them."""


@dataclass(frozen=True)
class TrialConfig:
    """Everything needed to regenerate a trial bit-for-bit.

    Attributes:
        scenario: "A" (drug works) or "B" (drug equals placebo; used for the damage demo).
        seed: RNG seed. Logged, so randomization is reproducible.
        n_sites: Number of trial sites.
        patients_per_site: Target enrollment per site.
        mechanisms: Leak-mechanism strengths keyed by name (see docs/assumptions.md),
            e.g. {"nausea_rr": 2.5, "titration": True, "local_glucose": True, "cold_chain": True}.
            An empty dict means all mechanisms off (the control scenario).
    """

    scenario: Literal["A", "B"]
    seed: int = 2026
    n_sites: int = 20
    patients_per_site: int = 40
    mechanisms: dict = field(default_factory=dict)


@dataclass
class Trial:
    """A generated trial: its tables and the config that produced them.

    Ground truth (who got the drug) is NOT an attribute of Trial. It lives in a locked
    table and is read only through `evals.ground_truth.ground_truth(trial_id)`, so no
    view, attacker, or classifier can accidentally see it.

    Attributes:
        trial_id: Stable ID, e.g. "tr_2026_B".
        tables: Table name -> DataFrame, keyed by the names in TABLES.
        config: The TrialConfig that generated this trial.
    """

    trial_id: str
    tables: dict[str, pd.DataFrame]
    config: TrialConfig


def generate_trial(config: TrialConfig) -> Trial:
    """Build a trial from NHANES physiology plus the seeded trial layer.

    Writes the trial tables and the locked ground-truth table to the DB.
    """
    raise NotImplementedError(f"owner: {OWNER}")


def load_trial(trial_id: str) -> Trial:
    """Load a previously generated trial from the DB (without ground truth)."""
    raise NotImplementedError(f"owner: {OWNER}")

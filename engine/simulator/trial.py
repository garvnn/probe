"""Trial config, the Trial container, and generate/load entry points. Owner: Garv."""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from engine.simulator import store
from engine.simulator.build import build_tables
from engine.simulator.schema import SCHEMA

OWNER = "Garv"

TABLES = tuple(SCHEMA)
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


def trial_id_for(config: TrialConfig) -> str:
    """Deterministic ID: `tr_<seed>_<scenario>`, plus `_off` when every mechanism is off and
    `_<sites>x<patients>` for a non-default size. Regenerating the same config overwrites it."""
    trial_id = f"tr_{config.seed}_{config.scenario}"
    if not config.mechanisms:
        trial_id += "_off"
    if (config.n_sites, config.patients_per_site) != (20, 40):
        trial_id += f"_{config.n_sites}x{config.patients_per_site}"
    return trial_id


def generate_trial(config: TrialConfig) -> Trial:
    """Build a trial from baseline physiology plus the seeded trial layer (see engine.simulator.build).

    Writes the trial tables and the locked ground-truth table to the DB.
    """
    if config.scenario not in ("A", "B"):
        raise ValueError(f"scenario must be 'A' or 'B', got {config.scenario!r}")
    if not 1 <= config.n_sites <= 99:
        raise ValueError(f"n_sites must be 1-99, got {config.n_sites}")
    if config.mechanisms:
        warnings.warn("leak mechanisms are not implemented yet; generating with all mechanisms off", stacklevel=2)

    trial_id = trial_id_for(config)
    rng = np.random.default_rng(config.seed)
    tables, arm, hidden = build_tables(trial_id, config.scenario, config.n_sites, config.patients_per_site, rng)
    ground_truth = pd.DataFrame({"patient_id": arm.index, "arm": arm.to_numpy()})
    store.save_trial(trial_id, asdict(config), tables, ground_truth, hidden)
    return Trial(trial_id=trial_id, tables=tables, config=config)


def load_trial(trial_id: str) -> Trial:
    """Load a previously generated trial from the DB (without ground truth)."""
    config = TrialConfig(**store.load_config(trial_id))
    return Trial(trial_id=trial_id, tables=store.load_tables(trial_id), config=config)

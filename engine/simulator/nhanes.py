"""Load and filter NHANES into the physiology base. Owner: Garv.

Files: DEMO, GHB, GLU, BMX, BPX/BPXO, merged on SEQN. Exact file names change between cycles;
verify them for the cycle you download (scripts/download_nhanes.py).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OWNER = "Garv"

RAW_DIR = Path("data/raw")
CORE_FIELDS = ("age", "sex", "bmi", "weight", "sbp", "dbp", "hba1c", "glucose")


def load_nhanes(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Merge the NHANES files on SEQN and return one row per participant with CORE_FIELDS."""
    raise NotImplementedError(f"owner: {OWNER}")


def filter_base(df: pd.DataFrame) -> pd.DataFrame:
    """Keep adults 30-75 with diabetes-range HbA1c; drop rows missing core fields."""
    raise NotImplementedError(f"owner: {OWNER}")


def sample_patients(base: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Sample n patients with replacement plus small jitter, so no NHANES row maps 1:1 to a patient."""
    raise NotImplementedError(f"owner: {OWNER}")

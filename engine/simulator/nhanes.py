"""Load and filter NHANES into the physiology base. Owner: Garv.

Files: DEMO, GHB, GLU, BMX, BPXO, merged on SEQN (see scripts/download_nhanes.py for cycles and URLs).
The filtered base is committed at data/processed/nhanes_base.csv so trials are identical on every
machine; the generator reads that, not the raw files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OWNER = "Garv"

RAW_DIR = Path("data/raw")
BASE_PATH = Path("data/processed/nhanes_base.csv")
CORE_FIELDS = ("age", "sex", "bmi", "weight", "height", "sbp", "dbp", "hba1c")
"""Required for a participant to enter the base. Fasting glucose is only measured in a morning
subsample, so it is kept when present (`glucose`) but not required."""
AGE_RANGE = (30, 75)
HBA1C_RANGE = (7.0, 10.5)

JITTER = {"age": 1.0, "bmi": 0.4, "hba1c": 0.1, "sbp": 3.0, "dbp": 2.0}
"""SD of the noise added when sampling, so no NHANES row maps 1:1 to a trial patient."""


def _read(path: Path) -> pd.DataFrame:
    return pd.read_sas(path, format="xport")


def load_nhanes(raw_dir: Path = RAW_DIR, cycle: str = "2017-2020") -> pd.DataFrame:
    """Merge the NHANES files on SEQN and return one row per participant with CORE_FIELDS (+ glucose)."""
    from scripts.download_nhanes import CYCLES

    _, files = CYCLES[cycle]
    path = {role: raw_dir / f"{name}.xpt" for role, name in files.items()}
    missing = [str(p) for p in path.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing NHANES files {missing}; run python -m scripts.download_nhanes")

    demo = _read(path["demo"])[["SEQN", "RIAGENDR", "RIDAGEYR"]]
    ghb = _read(path["ghb"])[["SEQN", "LBXGH"]]
    bmx = _read(path["bmx"])[["SEQN", "BMXWT", "BMXHT", "BMXBMI"]]
    bpx = _read(path["bpx"])
    sys_cols = [c for c in bpx.columns if c.startswith(("BPXOSY", "BPXSY"))]
    dia_cols = [c for c in bpx.columns if c.startswith(("BPXODI", "BPXDI"))]
    bp = pd.DataFrame({"SEQN": bpx["SEQN"], "sbp": bpx[sys_cols].mean(axis=1), "dbp": bpx[dia_cols].mean(axis=1)})
    glu = _read(path["glu"])[["SEQN", "LBXGLU"]]

    df = demo.merge(ghb, on="SEQN").merge(bmx, on="SEQN").merge(bp, on="SEQN", how="left").merge(glu, on="SEQN", how="left")
    return pd.DataFrame(
        {
            "seqn": df["SEQN"].astype(int),
            "age": df["RIDAGEYR"],
            "sex": df["RIAGENDR"].map({1.0: "M", 2.0: "F"}),
            "bmi": df["BMXBMI"],
            "weight": df["BMXWT"],
            "height": df["BMXHT"] / 100.0,
            "sbp": df["sbp"],
            "dbp": df["dbp"],
            "hba1c": df["LBXGH"],
            "glucose": df["LBXGLU"],
        }
    )


def filter_base(df: pd.DataFrame) -> pd.DataFrame:
    """Keep adults 30-75 with diabetes-range HbA1c; drop rows missing core fields."""
    keep = df["age"].between(*AGE_RANGE) & df["hba1c"].between(*HBA1C_RANGE)
    return df[keep].dropna(subset=list(CORE_FIELDS)).reset_index(drop=True)


def build_base(cycle: str = "2017-2020", raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """load_nhanes + filter_base, rounded for the committed CSV."""
    base = filter_base(load_nhanes(raw_dir, cycle))
    return base.round({"bmi": 1, "weight": 1, "height": 3, "sbp": 1, "dbp": 1, "hba1c": 1, "glucose": 0})


def load_base(path: Path = BASE_PATH) -> pd.DataFrame:
    """The committed physiology base."""
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run python -m scripts.download_nhanes")
    return pd.read_csv(path)


def sample_patients(base: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Sample n patients with replacement plus small jitter, so no NHANES row maps 1:1 to a patient.

    Returns columns age, sex, bmi, weight, height, sbp, dbp, hba1c (no seqn). Ranges stay inside
    the base filter; weight is recomputed from jittered BMI so the two stay consistent.
    """
    rows = base.iloc[rng.integers(0, len(base), n)].reset_index(drop=True)
    out = pd.DataFrame({"sex": rows["sex"], "height": rows["height"]})
    out["age"] = np.clip(np.rint(rows["age"] + rng.normal(0, JITTER["age"], n)), *AGE_RANGE).astype(int)
    out["bmi"] = np.clip(rows["bmi"] + rng.normal(0, JITTER["bmi"], n), 16.0, None).round(1)
    out["weight"] = out["bmi"] * out["height"] ** 2
    out["hba1c"] = np.clip(rows["hba1c"] + rng.normal(0, JITTER["hba1c"], n), *HBA1C_RANGE).round(1)
    out["sbp"] = rows["sbp"] + rng.normal(0, JITTER["sbp"], n)
    out["dbp"] = rows["dbp"] + rng.normal(0, JITTER["dbp"], n)
    return out[["age", "sex", "bmi", "weight", "height", "sbp", "dbp", "hba1c"]]

"""Site data container, the SiteCheck interface every check implements, and shared helpers. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

SCORE_CLIP = 10.0
"""Scores are clipped to [-SCORE_CLIP, SCORE_CLIP]; degenerate data (e.g. zero variance) scores the max."""


@dataclass
class SiteData:
    """All tables for one site.

    Attributes:
        site_id: Site identifier, e.g. "S07".
        tables: Table name -> DataFrame, filtered to this site's patients.
        arms: See below.
    """

    site_id: str
    tables: dict[str, pd.DataFrame]
    arms: pd.Series | None = None
    """Fake sites only: the attacker's own drug/placebo split (patient_id -> arm), from its optional
    ground_truth table. Never seen by the checks; used only to measure damage. None for real sites,
    whose arms live in the locked ground truth."""
    _cache: dict = field(default_factory=dict, repr=False, compare=False)
    """Per-site derived data (patient summaries, check statistics). Checks fill it lazily."""


@runtime_checkable
class SiteCheck(Protocol):
    """One forensic check. Droid-written checks must implement this too."""

    name: str

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        """Return a z-like score for `site` against `reference` sites. Higher = more suspicious.

        Under the null (a real site), scores should be roughly standard normal, so different checks
        are comparable and one threshold can apply to all of them.
        """
        ...


def others(site: SiteData, reference: list[SiteData]) -> list[SiteData]:
    """Reference sites excluding `site` itself (a real site is never scored against itself)."""
    return [r for r in reference if r.site_id != site.site_id]


def robust_z(x: float, ref: np.ndarray) -> float:
    """(x - median) / (1.4826 * MAD) of `ref`, clipped. NaN x (statistic not computable) scores the max."""
    ref = np.asarray(ref, dtype=float)
    ref = ref[np.isfinite(ref)]
    if not np.isfinite(x):
        return SCORE_CLIP
    if len(ref) < 3:
        return 0.0
    med = np.median(ref)
    scale = 1.4826 * np.median(np.abs(ref - med))
    scale = max(scale, 1e-9, 1e-3 * abs(med))
    return float(np.clip((x - med) / scale, -SCORE_CLIP, SCORE_CLIP))


def clip_score(z: float) -> float:
    """Clip a z-like score; NaN means the data was degenerate, which is itself suspicious."""
    if not np.isfinite(z):
        return SCORE_CLIP
    return float(np.clip(z, -SCORE_CLIP, SCORE_CLIP))


def scheduled_vitals(site: SiteData) -> pd.DataFrame:
    """Vitals at scheduled visits with patient_id and date, ordered by patient then date. Cached."""
    if "vitals" not in site._cache:
        visits = site.tables["visits"]
        v = site.tables["vitals"].merge(visits[visits["scheduled"].astype(bool)][["visit_id", "patient_id", "date"]], on="visit_id")
        site._cache["vitals"] = v.sort_values(["patient_id", "date"]).reset_index(drop=True)
    return site._cache["vitals"]


def patient_summary(site: SiteData) -> pd.DataFrame:
    """One row per patient with the variables the checks compare. Cached.

    Columns: age, bmi, baseline_hba1c, sbp, dbp, weight (means over scheduled visits), sbp_within_sd,
    hba1c_central (mean central HbA1c), glucose_central (mean central fasting glucose).
    """
    if "summary" not in site._cache:
        p = site.tables["patients"].set_index("patient_id")[["age", "bmi", "baseline_hba1c"]].astype(float)
        vit = scheduled_vitals(site).groupby("patient_id")
        p = p.join(vit[["sbp", "dbp", "weight"]].mean()).join(vit["sbp"].std().rename("sbp_within_sd"))
        labs = site.tables["labs"].merge(site.tables["visits"][["visit_id", "patient_id"]], on="visit_id")
        central = labs[labs["source"] == "central"].pivot_table(index="patient_id", columns="test", values="value", aggfunc="mean")
        p["hba1c_central"] = central.get("hba1c")
        p["glucose_central"] = central.get("glucose_fasting")
        site._cache["summary"] = p
    return site._cache["summary"]


def pooled_summary(reference: list[SiteData]) -> pd.DataFrame:
    """All reference sites' patient summaries stacked."""
    return pd.concat([patient_summary(r) for r in reference])

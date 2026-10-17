"""Primary analysis: ANCOVA on week-24 HbA1c change. Owner: Garv.

The trial's own end-of-study analysis: unblinded, so it reads the locked ground truth for real sites.
Fake sites bring their own arms (SiteData.arms, from the attacker's optional ground_truth table).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.formula.api as smf

from engine.fraud_checks.base import SiteData
from engine.simulator.trial import Trial

OWNER = "Garv"

ENDPOINT_VISIT = "Week 24"
MODEL = "change ~ C(arm, Treatment(reference='placebo')) + baseline_hba1c + C(site)"
TERM = "C(arm, Treatment(reference='placebo'))[T.drug]"


@dataclass
class PrimaryResult:
    """One ANCOVA fit.

    Attributes:
        effect: Adjusted drug − placebo difference in HbA1c change at Week 24 (points). Negative means
            the drug lowered HbA1c more than placebo.
        p: Two-sided p-value for the arm term.
        ci95: 95% confidence interval for `effect`.
        n: Patients analyzed (randomized, with a Week 24 central HbA1c).
        n_fake: How many of them came from fake sites.
    """

    effect: float
    p: float
    ci95: tuple[float, float]
    n: int
    n_fake: int = 0


def outcome_frame(tables: dict[str, pd.DataFrame], arms: pd.Series) -> pd.DataFrame:
    """One row per patient with an arm and a Week 24 central HbA1c: patient_id, site, arm, baseline_hba1c, change."""
    labs = tables["labs"].merge(tables["visits"][["visit_id", "patient_id", "visit_name"]], on="visit_id")
    wk24 = labs[(labs["test"] == "hba1c") & (labs["source"] == "central") & (labs["visit_name"] == ENDPOINT_VISIT)]
    wk24 = wk24.groupby("patient_id")["value"].first().rename("hba1c_wk24")
    df = tables["patients"][["patient_id", "site_id", "baseline_hba1c"]].merge(wk24, left_on="patient_id", right_index=True)
    df["arm"] = df["patient_id"].map(arms)
    df = df.dropna(subset=["arm", "hba1c_wk24", "baseline_hba1c"])
    df["change"] = df["hba1c_wk24"] - df["baseline_hba1c"]
    return df.rename(columns={"site_id": "site"})[["patient_id", "site", "arm", "baseline_hba1c", "change"]]


def analysis_frame(trial: Trial, extra_sites: list[SiteData] | None = None) -> pd.DataFrame:
    """Real patients plus any fake sites' patients. Each fake is its own site in the model, even when
    several fakes share a site_id (every round's fake is named the same); fakes without arms are left out."""
    from evals.ground_truth import ground_truth

    frames = [outcome_frame(trial.tables, ground_truth(trial.trial_id)).assign(fake=False)]
    for i, fake in enumerate(extra_sites or [], start=1):
        if fake.arms is None:
            continue
        frames.append(outcome_frame(fake.tables, fake.arms).assign(site=f"{fake.site_id}~fake{i}", fake=True))
    return pd.concat(frames, ignore_index=True)


def fit(df: pd.DataFrame) -> PrimaryResult:
    """ANCOVA on an analysis frame."""
    model = smf.ols(MODEL, data=df).fit()
    lo, hi = model.conf_int().loc[TERM]
    return PrimaryResult(
        effect=float(model.params[TERM]), p=float(model.pvalues[TERM]), ci95=(float(lo), float(hi)), n=len(df), n_fake=int(df["fake"].sum())
    )


def primary_result(trial: Trial, extra_sites: list[SiteData] | None = None) -> PrimaryResult:
    """The full ANCOVA result, real sites plus `extra_sites`."""
    return fit(analysis_frame(trial, extra_sites))


def primary_analysis(trial: Trial, extra_sites: list[SiteData] | None = None) -> tuple[float, float]:
    """ANCOVA: week-24 HbA1c change ~ arm + baseline HbA1c + site (as factor).

    `extra_sites` are fake sites to include alongside the real ones. Returns (effect_estimate, p_value).
    """
    result = primary_result(trial, extra_sites)
    return result.effect, result.p

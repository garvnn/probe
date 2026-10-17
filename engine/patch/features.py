"""Site-level features for the learned check. Owner: Garv.

Each feature is relative: a site statistic as a robust z-score against the other sites in the same
trial, plus the five core check scores. That puts honest sites from many simulated trials and fake
sites made against the demo trial on one scale.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.fraud_checks.base import SiteData, others, patient_summary, robust_z, scheduled_vitals
from engine.fraud_checks.checks_core import CORE_CHECKS, AutocorrelationCheck, VarianceCheck
from engine.simulator.schema import VISIT_SCHEDULE

OWNER = "Garv"

STAT_LABELS: dict[str, str] = {
    "log_sd_baseline_hba1c": "spread of baseline HbA1c",
    "log_sd_bmi": "spread of BMI",
    "log_sd_sbp": "spread of patients' average SBP",
    "log_sd_within_sbp": "visit-to-visit SBP variability",
    "autocorr_sbp": "SBP visit-to-visit autocorrelation",
    "autocorr_weight": "weight visit-to-visit autocorrelation",
    "corr_sbp_dbp": "SBP-DBP correlation",
    "corr_weight_bmi": "weight-BMI correlation",
    "corr_glucose_hba1c": "fasting glucose-HbA1c correlation",
    "mean_age": "average age",
    "mean_bmi": "average BMI",
    "mean_baseline_hba1c": "average baseline HbA1c",
    "mean_sbp": "average SBP",
    "hba1c_change_mean": "average HbA1c change by Week 24",
    "hba1c_change_sd": "spread of HbA1c change by Week 24",
    "complete_record_share": "share of patients with every scheduled visit",
    "dropout_share": "share of patients who left before Week 24",
    "unscheduled_per_patient": "unscheduled visits per patient",
    "ae_per_patient": "adverse events per patient",
    "conmed_per_patient": "concomitant medications per patient",
    "dispensing_per_patient": "dispensing events per patient",
    "weekend_visit_share": "share of visits on weekends",
    "window_dev_sd": "spread of visit timing around the schedule (days)",
    "draw_time_sd": "spread of lab draw times (minutes)",
    "fingerstick_within_sd": "visit-to-visit fingerstick glucose variability",
    "digit_05_share": "share of BP readings ending in 0 or 5",
    "kit_temp_sd": "spread of refrigerated kit temperatures",
}
"""Statistic -> plain-English label (what explain() and the UI show)."""

BINOMIAL_STATS = ("dropout_share",)
"""Small proportions whose spread across sites is mostly sampling noise: scored as a binomial z
against the pooled reference rate instead of a robust z (whose MAD is often zero)."""

CHECK_FEATURES = tuple(f"check_{c.name}" for c in CORE_CHECKS)
FEATURES = tuple(f"z_{s}" for s in STAT_LABELS) + CHECK_FEATURES


def label(feature: str) -> str:
    if feature.startswith("check_"):
        return f"core check '{feature[6:]}' score"
    return STAT_LABELS[feature[2:]]


def _corr(df: pd.DataFrame, a: str, b: str) -> float:
    pair = df[[a, b]].dropna()
    if len(pair) < 6 or pair[a].std() == 0 or pair[b].std() == 0:
        return np.nan
    return float(np.arctanh(np.clip(pair[a].corr(pair[b]), -0.999999, 0.999999)))


def _log(x: float) -> float:
    return float(np.log(x)) if np.isfinite(x) and x > 0 else np.nan


def site_stats(site: SiteData) -> dict[str, float]:
    """Raw per-site statistics (see STAT_LABELS). Cached on the SiteData."""
    if "patch_stats" in site._cache:
        return site._cache["patch_stats"]
    t = site.tables
    s = patient_summary(site)
    n = max(len(t["patients"]), 1)
    var = VarianceCheck._stat(site)
    ac = AutocorrelationCheck._stat(site)
    visits = t["visits"]
    sched = visits[visits["scheduled"].astype(bool)]

    labs = t["labs"].merge(visits[["visit_id", "patient_id", "visit_name", "date"]], on="visit_id")
    wk24 = labs[(labs["test"] == "hba1c") & (labs["source"] == "central") & (labs["visit_name"] == "Week 24")]
    change = wk24.groupby("patient_id")["value"].first() - t["patients"].set_index("patient_id")["baseline_hba1c"]
    change = change.dropna()

    per_patient = sched.groupby("patient_id")["visit_name"].nunique().reindex(t["patients"]["patient_id"], fill_value=0)
    has_wk24 = sched[sched["visit_name"] == "Week 24"]["patient_id"].unique()

    baseline = sched[sched["visit_name"] == "Baseline"].set_index("patient_id")["date"]
    target = sched["visit_name"].map(VISIT_SCHEDULE)
    dev = (sched["date"] - sched["patient_id"].map(baseline)).dt.days - target
    dev = dev[~sched["visit_name"].isin(["Screening", "Baseline"])].dropna()

    minutes = labs["draw_time"].dropna().astype(str).str.split(":", expand=True)
    draw_min = (minutes[0].astype(float) * 60 + minutes[1].astype(float)) if len(minutes) else pd.Series(dtype=float)
    finger = labs[labs["test"] == "glucose_fingerstick"].groupby("patient_id")["value"].std()

    fridge = t["kit_storage"].loc[t["kit_storage"]["storage"] == "refrigerated", "temp_c"]
    vit = scheduled_vitals(site)
    last = pd.concat([vit["sbp"], vit["dbp"]]).dropna().astype(int).to_numpy() % 10

    stats = {
        "log_sd_baseline_hba1c": var["baseline_hba1c"],
        "log_sd_bmi": var["bmi"],
        "log_sd_sbp": var["sbp"],
        "log_sd_within_sbp": var["sbp_within_sd"],
        "autocorr_sbp": ac["sbp"],
        "autocorr_weight": ac["weight"],
        "corr_sbp_dbp": _corr(s, "sbp", "dbp"),
        "corr_weight_bmi": _corr(s, "weight", "bmi"),
        "corr_glucose_hba1c": _corr(s, "glucose_central", "hba1c_central"),
        "mean_age": float(s["age"].mean()),
        "mean_bmi": float(s["bmi"].mean()),
        "mean_baseline_hba1c": float(s["baseline_hba1c"].mean()),
        "mean_sbp": float(s["sbp"].mean()),
        "hba1c_change_mean": float(change.mean()) if len(change) else np.nan,
        "hba1c_change_sd": float(change.std()) if len(change) > 1 else np.nan,
        "complete_record_share": float((per_patient >= len(VISIT_SCHEDULE)).mean()),
        "dropout_share": float(1 - len(has_wk24) / n),
        "unscheduled_per_patient": float((~visits["scheduled"].astype(bool)).sum() / n),
        "ae_per_patient": len(t["adverse_events"]) / n,
        "conmed_per_patient": len(t["conmeds"]) / n,
        "dispensing_per_patient": len(t["dispensing"]) / n,
        "weekend_visit_share": float((visits["date"].dt.weekday >= 5).mean()) if len(visits) else np.nan,
        "window_dev_sd": float(dev.std()) if len(dev) > 1 else np.nan,
        "draw_time_sd": float(draw_min.std()) if len(draw_min) > 1 else np.nan,
        "fingerstick_within_sd": float(finger.median()) if finger.notna().any() else np.nan,
        "digit_05_share": float(np.isin(last, (0, 5)).mean()) if len(last) else np.nan,
        "kit_temp_sd": float(fridge.std()) if len(fridge) > 1 else np.nan,
        "_n_patients": float(n),
    }
    site._cache["patch_stats"] = stats
    return stats


def site_features(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    """FEATURES for `site`: each statistic as a robust z against the reference sites (excluding the
    site itself), plus the core check scores."""
    refs = others(site, reference)
    mine = site_stats(site)
    ref_stats = [site_stats(r) for r in refs]
    out = {}
    for k in STAT_LABELS:
        if k in BINOMIAL_STATS:
            n = sum(r["_n_patients"] for r in ref_stats)
            rate = sum(r[k] * r["_n_patients"] for r in ref_stats) / n if n else np.nan
            se = np.sqrt(max(rate * (1 - rate), 1e-4) / mine["_n_patients"])
            out[f"z_{k}"] = float(np.clip((mine[k] - rate) / se, -10, 10)) if np.isfinite(mine[k]) else 10.0
        else:
            out[f"z_{k}"] = robust_z(mine[k], np.array([r[k] for r in ref_stats]))
    for check in CORE_CHECKS:
        out[f"check_{check.name}"] = float(np.clip(check().score(site, refs), -10, 10))
    return out


def feature_frame(pairs: list[tuple[SiteData, list[SiteData]]]) -> pd.DataFrame:
    """One row of FEATURES per (site, reference) pair."""
    return pd.DataFrame([site_features(site, ref) for site, ref in pairs], columns=list(FEATURES))

"""Why a Sentinel check fired, in numbers the attacker can act on. Owner: Shreyas.

For each check, `explain(site, reference)` reports the interpretable quantities behind the check's
score on the fake site next to their typical range on the real sites (10th-90th percentile across
sites). That's aggregates only: never a real site's rows, never an arm. It reuses Sentinel's own
statistics (patient_summary, VarianceCheck._stat, AutocorrelationCheck._stat) so the numbers
match what the check actually scored.

The loop prefers a check's own `explain` method if it has one, then this registry, then just the
check's name, so Sentinel checks can take this over later without changing the loop.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from engine.fraud_checks.base import SiteData, others, patient_summary, pooled_summary, scheduled_vitals
from engine.fraud_checks.checks_core import AutocorrelationCheck, CorrelationStructureCheck, InlierCheck, VarianceCheck

OWNER = "Shreyas"

Measures = Callable[[SiteData, list[SiteData]], dict[str, float]]
"""(site, reference) -> label -> value. `reference` is passed for measures relative to the real sites."""


def _typical(values: list[float], digits: int) -> list[float]:
    v = np.array([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [round(float(np.percentile(v, 10)), digits) + 0.0, round(float(np.percentile(v, 90)), digits) + 0.0]


def _row(label: str, yours: float, real: list[float], digits: int = 2) -> dict:
    lo, hi = _typical(real, digits)
    yours = round(float(yours), digits) if yours is not None and np.isfinite(yours) else None
    position = "not computable (too little data)" if yours is None else "below" if yours < lo else "above" if yours > hi else "within"
    return {"measure": label, "your_site": yours, "real_sites_typical": [lo, hi], "position": position}


def _sentence(row: dict) -> str:
    lo, hi = (x + 0.0 for x in row["real_sites_typical"])  # + 0.0 turns -0.0 into 0.0
    span = f"{lo} to {hi}" if lo < 0 or hi < 0 else f"{lo}-{hi}"
    return f"{row['measure']} on your site: {row['your_site']}, real sites: {span}"


# ---------------------------------------------------------------- per-check measures


def _digits(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    v = scheduled_vitals(site)
    last = pd.concat([v["sbp"], v["dbp"]]).dropna().astype(int).to_numpy() % 10
    if len(last) == 0:
        return {"share of BP readings ending in 0 or 5": np.nan, "share of the most common BP last digit": np.nan}
    return {
        "share of BP readings ending in 0 or 5": float(np.isin(last, (0, 5)).mean()),
        "share of the most common BP last digit": float(np.bincount(last, minlength=10).max() / len(last)),
    }


VARIANCE_LABELS = {
    "baseline_hba1c": "SD of baseline HbA1c across patients",
    "bmi": "SD of BMI across patients",
    "sbp": "SD of patients' mean SBP",
    "sbp_within_sd": "median within-patient SD of SBP across visits",
}


def _variance(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    logs = VarianceCheck._stat(site)
    return {VARIANCE_LABELS[k]: float(np.exp(v)) for k, v in logs.items()}


def _inlier(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    cols = InlierCheck.VARIABLES
    pooled = pooled_summary(others(site, reference))[cols].dropna()
    mean, inv = pooled.mean().to_numpy(), np.linalg.pinv(np.cov(pooled.to_numpy(), rowvar=False))
    x = patient_summary(site)[cols].dropna().to_numpy() - mean
    d = np.sqrt(np.einsum("ij,jk,ik->i", x, inv, x)) if len(x) else np.array([np.nan])
    s = patient_summary(site)
    out = {"median distance of your patients from the typical patient (Mahalanobis over age, BMI, HbA1c, SBP, DBP)": float(np.median(d))}
    out |= {f"SD of patient {c}": float(s[c].std()) for c in cols}
    return out


CORR_LABELS = {
    ("sbp", "dbp"): "correlation of patients' mean SBP and mean DBP",
    ("weight", "bmi"): "correlation of patients' mean weight and BMI",
    ("glucose_central", "hba1c_central"): "correlation of patients' mean central fasting glucose and central HbA1c",
}


def _corr(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    s = patient_summary(site)
    out = {}
    for a, b in CorrelationStructureCheck.PAIRS:
        pair = s[[a, b]].dropna()
        ok = len(pair) >= 6 and pair[a].std() > 0 and pair[b].std() > 0
        out[CORR_LABELS[(a, b)]] = float(pair[a].corr(pair[b])) if ok else np.nan
    return out


def _autocorr(site: SiteData, reference: list[SiteData]) -> dict[str, float]:
    stat = AutocorrelationCheck._stat(site)
    return {f"median lag-1 autocorrelation of each patient's {v} across visits": float(stat[v]) for v in AutocorrelationCheck.VARIABLES}


MEASURES: dict[str, Measures] = {
    "digit_pref": _digits,
    "variance": _variance,
    "inlier": _inlier,
    "corr_struct": _corr,
    "autocorr": _autocorr,
}


def explain(check_name: str, site: SiteData, reference: list[SiteData]) -> dict | None:
    """What `check_name` measured on `site` vs the typical range on `reference`, or None if unknown."""
    measures = MEASURES.get(check_name)
    if measures is None:
        return None
    yours = measures(site, reference)
    real = [measures(r, reference) for r in reference]
    rows = [_row(label, value, [r[label] for r in real]) for label, value in yours.items()]
    off = [r for r in rows if r["position"] != "within"] or rows
    return {"check": check_name, "measures": rows, "summary": "; ".join(_sentence(r) for r in off)}

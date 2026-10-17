"""Core forensic checks (published central statistical monitoring methods). Owner: Garv.

Every check returns a z-like score: roughly standard normal for a real site, higher = more suspicious.
Checks that compare against other sites use robust z-scores (median / MAD) over the reference sites;
checks with a known null distribution convert their p-value to z. Per-site statistics are cached on
the SiteData, so scoring many sites against the same reference is cheap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from engine.fraud_checks.base import SCORE_CLIP, SiteData, clip_score, others, patient_summary, pooled_summary, robust_z, scheduled_vitals

OWNER = "Garv"


def _p_to_z(p: float) -> float:
    """One-sided p-value -> z (p = 0.5 -> 0). Tiny p clips at SCORE_CLIP; p = 1 gives about −7, not −inf."""
    return clip_score(stats.norm.isf(float(np.clip(p, 1e-300, 1.0 - 1e-12))))


def _stouffer(zs: list[float]) -> float:
    zs = [z for z in zs if np.isfinite(z)]
    return clip_score(sum(zs) / np.sqrt(len(zs))) if zs else SCORE_CLIP


def _cached(site: SiteData, key: str, fn) -> float:
    if key not in site._cache:
        site._cache[key] = fn(site)
    return site._cache[key]


class TerminalDigitCheck:
    """Humans favor 0 and 5 in BP readings. χ² on last digit vs uniform."""

    name = "digit_pref"
    MIN_READINGS = 50

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        v = scheduled_vitals(site)
        readings = pd.concat([v["sbp"], v["dbp"]]).dropna().astype(int)
        if len(readings) < self.MIN_READINGS:
            return 0.0
        counts = np.bincount(readings.to_numpy() % 10, minlength=10)
        _, p = stats.chisquare(counts)
        return _p_to_z(p)


class VarianceCheck:
    """Fakes are too tidy. Site SD vs other sites (F / Levene).

    Compares the log SD of baseline HbA1c, BMI, mean SBP, and within-patient SBP variability against
    the other sites; low variance is suspicious. Per-variable robust z-scores are combined (Stouffer).
    """

    name = "variance"
    VARIABLES = ("baseline_hba1c", "bmi", "sbp", "sbp_within_sd")

    @staticmethod
    def _stat(site: SiteData) -> dict[str, float]:
        s = patient_summary(site)
        with np.errstate(divide="ignore"):  # zero spread -> -inf -> maximally tidy
            out = {v: float(np.log(s[v].std())) for v in VarianceCheck.VARIABLES if v != "sbp_within_sd"}
            out["sbp_within_sd"] = float(np.log(s["sbp_within_sd"].median()))
        return out

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        mine = _cached(site, "variance", self._stat)
        refs = [_cached(r, "variance", self._stat) for r in others(site, reference)]
        return _stouffer([-robust_z(mine[v], np.array([r[v] for r in refs])) for v in self.VARIABLES])


class InlierCheck:
    """Patients cluster near the mean. Mahalanobis distance distribution.

    Each patient's squared Mahalanobis distance from the pooled reference mean (age, BMI, baseline
    HbA1c, mean SBP, mean DBP); a site whose patients sit unusually close to the center (low mean
    log distance) is suspicious.
    """

    name = "inlier"
    VARIABLES = ["age", "bmi", "baseline_hba1c", "sbp", "dbp"]

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        refs = others(site, reference)
        pooled = pooled_summary(refs)[self.VARIABLES].dropna()
        mean = pooled.mean().to_numpy()
        inv = np.linalg.pinv(np.cov(pooled.to_numpy(), rowvar=False))

        def stat(s: SiteData) -> float:
            x = patient_summary(s)[self.VARIABLES].dropna().to_numpy() - mean
            if len(x) == 0:
                return np.nan
            d2 = np.einsum("ij,jk,ik->i", x, inv, x)
            return float(np.mean(np.log(d2 + 1e-9)))

        return -robust_z(stat(site), np.array([stat(r) for r in refs]))


class CorrelationStructureCheck:
    """Related variables lose their real relationship (SBP↔DBP, weight↔BMI, glucose↔HbA1c).

    For each pair, the site's correlation is compared with the pooled reference correlation via
    Fisher's z: (atanh r_site − atanh r_pooled)·√(n−3) is ~N(0,1) for a real site. The squared
    deviations sum to a χ² with one degree of freedom per pair, converted to a z-score.
    """

    name = "corr_struct"
    PAIRS = (("sbp", "dbp"), ("weight", "bmi"), ("glucose_central", "hba1c_central"))

    @staticmethod
    def _fisher(r: float) -> float:
        return float(np.arctanh(np.clip(r, -0.999999, 0.999999)))

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        mine = patient_summary(site)
        pooled = pooled_summary(others(site, reference))
        chi2, k = 0.0, 0
        for a, b in self.PAIRS:
            pair = mine[[a, b]].dropna()
            if len(pair) < 6 or pair[a].std() == 0 or pair[b].std() == 0:
                return SCORE_CLIP
            r_site = pair[a].corr(pair[b])
            r_ref = pooled[[a, b]].dropna().corr().iloc[0, 1]
            chi2 += ((self._fisher(r_site) - self._fisher(r_ref)) * np.sqrt(len(pair) - 3)) ** 2
            k += 1
        return _p_to_z(stats.chi2.sf(chi2, k))


class AutocorrelationCheck:
    """Visit-to-visit trajectories too smooth or too random. Lag-1 autocorrelation vs pooled.

    For SBP and weight, each patient's deviations from their own mean across scheduled visits give a
    lag-1 autocorrelation; the site's median is compared with the other sites in both directions.
    The smaller two-sided p-value (Šidák-corrected over the two variables) becomes the score.
    """

    name = "autocorr"
    VARIABLES = ("sbp", "weight")

    @staticmethod
    def _stat(site: SiteData) -> dict[str, float]:
        v = scheduled_vitals(site)
        out = {}
        for var in AutocorrelationCheck.VARIABLES:
            dev = v[var] - v.groupby("patient_id")[var].transform("mean")
            lag = dev.groupby(v["patient_id"]).shift(1)
            num = (dev * lag).groupby(v["patient_id"]).sum()
            den = (dev**2).groupby(v["patient_id"]).sum()
            ac = (num / den.replace(0, np.nan)).dropna()
            out[var] = float(ac.median()) if len(ac) else np.nan
        return out

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        mine = _cached(site, "autocorr", self._stat)
        refs = [_cached(r, "autocorr", self._stat) for r in others(site, reference)]
        p_min = 1.0
        for var in self.VARIABLES:
            z = robust_z(mine[var], np.array([r[var] for r in refs]))
            p_min = min(p_min, 2 * stats.norm.sf(abs(z)))
        return _p_to_z(1.0 - (1.0 - p_min) ** len(self.VARIABLES))  # Šidák: uniform under the null


CORE_CHECKS = (TerminalDigitCheck, VarianceCheck, InlierCheck, CorrelationStructureCheck, AutocorrelationCheck)

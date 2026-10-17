"""TEMPORARY stand-in check suite. NOT Sentinel. Never use it for reported results. Owner: Shreyas.

Four deliberately simple checks so the Impostor loop can be built and demoed before Garv's real
checks (checks_core.py / checks_rates.py / suite.py) land. When they do, delete this file and pass
the real CheckSuite to fake_data_loop; nothing else changes.

Every check returns a one-sided z-score against the reference sites (higher = more suspicious):

    digit_pref    SBP last-digit preference: chi-square vs uniform, as a Wilson-Hilferty z
                  (about N(0,1) for honest data, so no reference needed)
    variance      spread of SBP, DBP, weight, BMI, age, baseline HbA1c too LOW vs the reference
    corr_struct   SBP-DBP correlation too DIFFERENT (either direction) from the reference
    missingness   records too complete: share of patients with an imperfect record (a missed
                  scheduled visit or any unscheduled visit) too LOW vs the reference

combined = the largest check score, so a site is flagged when any single check crosses the
threshold, and `fired(threshold)` names exactly the checks that did.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.fraud_checks.base import SiteCheck, SiteData
from engine.fraud_checks.suite import CheckSuite, SiteScores
from engine.simulator.schema import VISIT_SCHEDULE

STANDIN = True
"""Marker: runs scored by this module are labeled stand-in in every saved file."""
SUITE_NAME = "standin (TEMPORARY, not Sentinel, not for results)"

SD_FLOOR = 1e-6
NO_DATA_SCORE = 10.0
"""A site too small or empty to compute a statistic is itself suspicious."""
CALIBRATION_MARGIN = 0.5
"""Threshold = highest leave-one-out score among the real sites + this margin."""


def _z(value: float, reference: list[float], direction: str) -> float:
    """One-sided (or absolute) z of `value` against `reference`. NaN value -> NO_DATA_SCORE."""
    if value is None or not np.isfinite(value):
        return NO_DATA_SCORE
    ref = np.array([r for r in reference if r is not None and np.isfinite(r)], dtype=float)
    if len(ref) < 2:
        return 0.0
    z = (value - ref.mean()) / max(ref.std(ddof=1), SD_FLOOR)
    if direction == "high":
        return float(max(z, 0.0))
    if direction == "low":
        return float(max(-z, 0.0))
    return float(abs(z))


class _StatCheck:
    """A check defined by a per-site statistic and which direction is suspicious."""

    name = "base"
    direction = "high"

    def statistic(self, site: SiteData) -> float:
        raise NotImplementedError

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        return _z(self.statistic(site), [self.statistic(r) for r in reference], self.direction)


class TerminalDigitCheck(_StatCheck):
    name = "digit_pref"
    direction = "high"
    DF = 9

    def statistic(self, site: SiteData) -> float:
        """Chi-square of SBP last digits vs uniform, mapped to a z by Wilson-Hilferty."""
        sbp = pd.to_numeric(site.tables["vitals"]["sbp"], errors="coerce").dropna().round().astype(int)
        if len(sbp) < 20:
            return float("nan")
        counts = np.bincount(np.abs(sbp.to_numpy()) % 10, minlength=10)
        expected = len(sbp) / 10
        chi2 = float(((counts - expected) ** 2 / expected).sum())
        k = self.DF
        return float(((chi2 / k) ** (1 / 3) - (1 - 2 / (9 * k))) / np.sqrt(2 / (9 * k)))

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        z = self.statistic(site)
        return NO_DATA_SCORE if not np.isfinite(z) else float(max(z, 0.0))


class LowVarianceCheck(_StatCheck):
    name = "variance"
    direction = "low"
    COLUMNS = (("vitals", "sbp"), ("vitals", "dbp"), ("vitals", "weight"), ("patients", "bmi"), ("patients", "age"), ("patients", "baseline_hba1c"))

    def statistic(self, site: SiteData) -> float:
        logs = []
        for table, col in self.COLUMNS:
            x = pd.to_numeric(site.tables[table][col], errors="coerce").dropna()
            if len(x) < 5:
                return float("nan")
            logs.append(np.log(max(float(x.std(ddof=1)), SD_FLOOR)))
        return float(np.mean(logs))


class CorrelationCheck(_StatCheck):
    name = "corr_struct"
    direction = "abs"

    def statistic(self, site: SiteData) -> float:
        v = site.tables["vitals"][["sbp", "dbp"]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(v) < 20 or v["sbp"].std() == 0 or v["dbp"].std() == 0:
            return float("nan")
        return float(np.corrcoef(v["sbp"], v["dbp"])[0, 1])


class MissingnessCheck(_StatCheck):
    name = "missingness"
    direction = "low"

    def statistic(self, site: SiteData) -> float:
        patients = site.tables["patients"]["patient_id"]
        if len(patients) < 5:
            return float("nan")
        v = site.tables["visits"]
        sched = v["scheduled"].astype(bool)
        attended = v[sched & v["visit_name"].isin(list(VISIT_SCHEDULE))].groupby("patient_id")["visit_name"].nunique()
        incomplete = attended.reindex(patients, fill_value=0) < len(VISIT_SCHEDULE)
        unscheduled = v[~sched].groupby("patient_id").size().reindex(patients, fill_value=0) > 0
        return float((incomplete.to_numpy() | unscheduled.to_numpy()).mean())


STANDIN_CHECKS: tuple[type[_StatCheck], ...] = (TerminalDigitCheck, LowVarianceCheck, CorrelationCheck, MissingnessCheck)


@dataclass
class StandinSiteScores(SiteScores):
    def fired(self, threshold: float) -> list[str]:
        return [name for name, s in self.per_check.items() if s >= threshold]


@dataclass
class StandinCheckSuite(CheckSuite):
    """TEMPORARY. Same interface as CheckSuite; combined = max check score."""

    name: str = field(default=SUITE_NAME)

    def score_site(self, site: SiteData, reference: list[SiteData]) -> StandinSiteScores:
        per_check = {c.name: round(float(c.score(site, reference)), 4) for c in self.checks}
        return StandinSiteScores(per_check=per_check, combined=max(per_check.values()) if per_check else 0.0)

    def false_alarm_rate(self, real_sites: list[SiteData]) -> float:
        """Leave-one-out: each real site scored against the others."""
        flagged = [self.score_site(s, [r for r in real_sites if r is not s]).combined >= self.threshold for s in real_sites]
        return float(np.mean(flagged)) if flagged else 0.0

    def with_check(self, check: SiteCheck) -> StandinCheckSuite:
        return StandinCheckSuite(checks=[*self.checks, check], threshold=self.threshold, version=self.version + 1)


def calibrate_standin(real_sites: list[SiteData], margin: float = CALIBRATION_MARGIN) -> StandinCheckSuite:
    """Build the stand-in suite with a threshold every real site passes (leave-one-out)."""
    suite = StandinCheckSuite(checks=[c() for c in STANDIN_CHECKS], threshold=float("inf"), version=0)
    loo = [suite.score_site(s, [r for r in real_sites if r is not s]).combined for s in real_sites]
    suite.threshold = round(max(loo) + margin, 4)
    return suite

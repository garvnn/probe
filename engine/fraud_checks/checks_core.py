"""Core forensic checks (published central statistical monitoring methods). Owner: Garv."""

from __future__ import annotations

from engine.fraud_checks.base import SiteData

OWNER = "Garv"


class TerminalDigitCheck:
    """Humans favor 0 and 5 in BP readings. χ² on last digit vs uniform."""

    name = "digit_pref"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class VarianceCheck:
    """Fakes are too tidy. Site SD vs other sites (F / Levene)."""

    name = "variance"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class InlierCheck:
    """Patients cluster near the mean. Mahalanobis distance distribution."""

    name = "inlier"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class CorrelationStructureCheck:
    """Related variables lose their real relationship (SBP↔DBP, weight↔BMI, glucose↔HbA1c)."""

    name = "corr_struct"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class AutocorrelationCheck:
    """Visit-to-visit trajectories too smooth or too random. Lag-1 autocorrelation vs pooled."""

    name = "autocorr"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


CORE_CHECKS = (TerminalDigitCheck, VarianceCheck, InlierCheck, CorrelationStructureCheck, AutocorrelationCheck)

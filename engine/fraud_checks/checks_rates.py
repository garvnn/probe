"""Rate-based checks: dates, AE reporting, missingness. Owner: Ajay."""

from __future__ import annotations

from engine.fraud_checks.base import SiteData

OWNER = "Ajay"


class DateAnomalyCheck:
    """Visits on weekends/holidays, perfect window adherence. Rate tests vs other sites."""

    name = "date_anomaly"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class AEUnderReportingCheck:
    """Fakers forget side effects. Poisson AE rate vs other sites."""

    name = "ae_rate"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


class MissingnessCheck:
    """Fakes have no missing data. Missing-rate z-score."""

    name = "missingness"

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")


RATE_CHECKS = (DateAnomalyCheck, AEUnderReportingCheck, MissingnessCheck)

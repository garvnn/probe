"""Fallback when Droid is unavailable: a small classifier wrapped as a SiteCheck. Owner: Ajay.

Same acceptance gate as a Droid-written check.
"""

from __future__ import annotations

from engine.detector.base import SiteData

OWNER = "Ajay"


class FallbackClassifierCheck:
    """Classifier on site-level features (real vs escaped fake), wrapped as a SiteCheck."""

    name = "fallback_clf"

    def fit(self, real_sites: list[SiteData], escaped_fakes: list[SiteData]) -> FallbackClassifierCheck:
        raise NotImplementedError(f"owner: {OWNER}")

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        raise NotImplementedError(f"owner: {OWNER}")

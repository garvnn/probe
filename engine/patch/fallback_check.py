"""The learned check: regularized logistic regression on site-level features, wrapped as a SiteCheck. Owner: Garv.

Trained on honest sites (many simulated trials) vs fake sites from Impostor runs. Its score is the
model's log-odds, standardized against the honest training sites, so like every Sentinel check it is
roughly standard normal on a real site and higher = more suspicious. Everything needed to rebuild it
(features, coefficients, standardization) is plain numbers, saved in the frozen suite file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.fraud_checks.base import SCORE_CLIP, SiteData, clip_score
from engine.patch.features import FEATURES, feature_frame, label, site_features

OWNER = "Garv"

DEFAULT_C = 0.3
"""Inverse L2 strength. Small on purpose: few fakes, many features."""
FEATURE_CLIP = 6.0
"""Features are clipped before the model so one degenerate statistic can't dominate."""


class FallbackClassifierCheck:
    """Classifier on site-level features (real vs fake), wrapped as a SiteCheck."""

    name = "learned"

    def __init__(self, params: dict | None = None) -> None:
        self.features: list[str] = list(FEATURES)
        self.coef = np.zeros(len(self.features))
        self.intercept = 0.0
        self.center, self.scale = 0.0, 1.0
        self.fitted = False
        self.train_info: dict = {}
        if params:
            self.features = list(params["features"])
            self.coef = np.asarray(params["coef"], dtype=float)
            self.intercept = float(params["intercept"])
            self.center, self.scale = float(params["center"]), float(params["scale"])
            self.train_info = dict(params.get("train_info", {}))
            self.fitted = True

    # ------------------------------------------------------------ training

    def fit_frames(self, real: pd.DataFrame, fake: pd.DataFrame, c: float = DEFAULT_C) -> FallbackClassifierCheck:
        """Fit on feature frames (rows = sites, columns = FEATURES). Classes are weighted equally."""
        from sklearn.linear_model import LogisticRegression

        X = np.clip(pd.concat([real, fake])[self.features].to_numpy(dtype=float), -FEATURE_CLIP, FEATURE_CLIP)
        y = np.r_[np.zeros(len(real)), np.ones(len(fake))]
        model = LogisticRegression(C=c, class_weight="balanced", max_iter=5000).fit(X, y)
        self.coef, self.intercept = model.coef_[0], float(model.intercept_[0])
        logits = self._logits(real)
        med = float(np.median(logits))
        self.center, self.scale = med, max(1.4826 * float(np.median(np.abs(logits - med))), 1e-6)
        self.fitted = True
        self.train_info = {"n_real": len(real), "n_fake": len(fake), "C": c}
        return self

    def fit(
        self, real: list[tuple[SiteData, list[SiteData]]], fakes: list[tuple[SiteData, list[SiteData]]], c: float = DEFAULT_C
    ) -> FallbackClassifierCheck:
        """Fit on (site, reference sites) pairs: honest sites vs fake sites."""
        return self.fit_frames(feature_frame(real), feature_frame(fakes), c)

    # ------------------------------------------------------------ scoring

    def _logits(self, frame: pd.DataFrame) -> np.ndarray:
        X = np.clip(frame[self.features].to_numpy(dtype=float), -FEATURE_CLIP, FEATURE_CLIP)
        return X @ self.coef + self.intercept

    def score_frame(self, frame: pd.DataFrame) -> np.ndarray:
        """Scores for precomputed feature rows (same scale as score())."""
        return np.clip((self._logits(frame) - self.center) / self.scale, -SCORE_CLIP, SCORE_CLIP)

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        if not self.fitted:
            raise RuntimeError("learned check is not fitted; train it with fit() or load it from a frozen suite")
        return clip_score(float(self.score_frame(pd.DataFrame([site_features(site, reference)]))[0]))

    def explain(self, site: SiteData, reference: list[SiteData], top: int = 3) -> dict:
        """The features that pushed this site's score up the most, in the loop's explain format."""
        feats = site_features(site, reference)
        x = np.clip(np.array([feats[f] for f in self.features]), -FEATURE_CLIP, FEATURE_CLIP)
        contrib = x * self.coef
        order = np.argsort(contrib)[::-1][:top]
        rows = [
            {
                "measure": label(self.features[i]),
                "your_site": round(float(x[i]), 2),
                "real_sites_typical": [-1.28, 1.28],
                "position": "above" if x[i] > 1.28 else "below" if x[i] < -1.28 else "within",
                "unit": "z vs the other sites in the trial",
            }
            for i in order
            if contrib[i] > 0
        ]
        summary = "; ".join(f"{r['measure']} at z = {r['your_site']}" for r in rows) or "no single feature stands out"
        return {"check": self.name, "measures": rows, "summary": f"learned check: {summary}"}

    # ------------------------------------------------------------ persistence

    def to_params(self) -> dict:
        return {
            "features": self.features,
            "coef": [round(float(v), 8) for v in self.coef],
            "intercept": round(self.intercept, 8),
            "center": round(self.center, 8),
            "scale": round(self.scale, 8),
            "train_info": self.train_info,
        }

    @classmethod
    def from_params(cls, params: dict) -> FallbackClassifierCheck:
        return cls(params)

    def top_weights(self, n: int = 8) -> list[tuple[str, float]]:
        """Largest positive weights (features that make a site look fake), for the report."""
        order = np.argsort(self.coef)[::-1][:n]
        return [(label(self.features[i]), round(float(self.coef[i]), 3)) for i in order]

"""Permutation null for arm-prediction accuracy. Owner: Ajay.

Labels are shuffled within each site (randomization is 1:1 within site, so this keeps each site's arm
balance), then the full grouped-CV pipeline is rerun on the same folds. p = (1 + #null >= observed) / (n + 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.blind_leak.classifier import CVResult, cross_validate, site_folds

OWNER = "Ajay"

DEFAULT_N = 200
FAST_N = 20
"""For unit tests only. Too few draws to report a p-value from."""


@dataclass
class PermutationResult:
    observed: CVResult
    null_accuracy: np.ndarray = field(repr=False)
    null_auc: np.ndarray = field(repr=False)
    null_lo: float
    """2.5th percentile of null accuracy."""
    null_hi: float
    """97.5th percentile of null accuracy."""
    p_value: float
    """Accuracy p-value."""
    p_value_auc: float
    n: int
    seed: int

    @property
    def accuracy_in_null(self) -> bool:
        return self.null_lo <= self.observed.accuracy <= self.null_hi


def shuffle_within(y: pd.Series, groups: pd.Series, rng: np.random.Generator) -> pd.Series:
    vals = y.to_numpy().copy()
    g = groups.to_numpy()
    for site in np.unique(g):
        idx = np.flatnonzero(g == site)
        vals[idx] = vals[rng.permutation(idx)]
    return pd.Series(vals, index=y.index, name=y.name)


def run_permutation(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n: int = DEFAULT_N,
    seed: int = 0,
    n_splits: int = 5,
) -> PermutationResult:
    folds = site_folds(groups, n_splits)
    observed = cross_validate(X, y, groups, seed=seed, folds=folds)
    rng = np.random.default_rng(seed)
    acc = np.empty(n)
    auc = np.empty(n)
    for i in range(n):
        r = cross_validate(X, shuffle_within(y, groups, rng), groups, seed=seed, folds=folds)
        acc[i], auc[i] = r.accuracy, r.auc
    lo, hi = np.percentile(acc, [2.5, 97.5]) if n else (np.nan, np.nan)
    return PermutationResult(
        observed=observed,
        null_accuracy=acc,
        null_auc=auc,
        null_lo=float(lo),
        null_hi=float(hi),
        p_value=float((1 + np.sum(acc >= observed.accuracy)) / (n + 1)),
        p_value_auc=float((1 + np.sum(auc >= observed.auc)) / (n + 1)),
        n=n,
        seed=seed,
    )


def permutation_test(X: pd.DataFrame, y: pd.Series, groups: pd.Series, n: int = DEFAULT_N, seed: int = 0) -> tuple[float, float, float]:
    """Shuffle labels `n` times. Return (null_lo, null_hi, p_value) for the observed accuracy."""
    r = run_permutation(X, y, groups, n=n, seed=seed)
    return r.null_lo, r.null_hi, r.p_value

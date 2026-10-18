"""Arm classifier with site-grouped cross-validation. Owner: Ajay.

Import lightgbm inside functions, not at module level (it needs libomp on macOS).

Folds come from GroupKFold on site_id, so no site (and therefore no patient) is in both train and test.
Everything is seeded; LightGBM runs single-threaded in deterministic mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

OWNER = "Ajay"

POSITIVE = "drug"

LGBM_PARAMS = dict(
    n_estimators=150,
    learning_rate=0.05,
    num_leaves=15,
    min_child_samples=20,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    n_jobs=1,
    deterministic=True,
    force_row_wise=True,
    verbose=-1,
)


@dataclass
class Fold:
    fold: int
    test_sites: list[str]
    train_sites: list[str]
    n_test: int
    accuracy: float
    auc: float


@dataclass
class CVResult:
    accuracy: float
    """Pooled out-of-fold accuracy."""
    auc: float
    """Pooled out-of-fold ROC AUC."""
    folds: list[Fold]
    oof_proba: pd.Series = field(repr=False)


def encode_labels(y: pd.Series) -> np.ndarray:
    """drug -> 1, placebo -> 0. Accepts 0/1 already."""
    if y.dtype == object or isinstance(y.dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(y):
        bad = set(y.unique()) - {"drug", "placebo"}
        if bad:
            raise ValueError(f"labels must be drug|placebo, got {sorted(bad)}")
        return (y.to_numpy() == POSITIVE).astype(int)
    return y.to_numpy().astype(int)


def make_model(seed: int):
    from lightgbm import LGBMClassifier

    return LGBMClassifier(random_state=seed, **LGBM_PARAMS)


def site_folds(groups: pd.Series, n_splits: int = 5) -> list[tuple[np.ndarray, np.ndarray]]:
    from sklearn.model_selection import GroupKFold

    k = min(n_splits, groups.nunique())
    if k < 2:
        raise ValueError("need at least 2 sites for grouped CV")
    return list(GroupKFold(n_splits=k).split(np.zeros(len(groups)), groups=groups.to_numpy()))


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = 5,
    seed: int = 0,
    folds: list[tuple[np.ndarray, np.ndarray]] | None = None,
) -> CVResult:
    from sklearn.metrics import accuracy_score, roc_auc_score

    yy = encode_labels(y)
    folds = folds if folds is not None else site_folds(groups, n_splits)
    g = groups.to_numpy()
    oof = np.full(len(yy), np.nan)
    out: list[Fold] = []
    for i, (tr, te) in enumerate(folds):
        model = make_model(seed + i)
        model.fit(X.iloc[tr], yy[tr])
        p = model.predict_proba(X.iloc[te])[:, 1]
        oof[te] = p
        out.append(Fold(
            fold=i,
            test_sites=sorted(set(g[te])),
            train_sites=sorted(set(g[tr])),
            n_test=len(te),
            accuracy=float(accuracy_score(yy[te], p >= 0.5)),
            auc=_auc(yy[te], p, roc_auc_score),
        ))
    return CVResult(
        accuracy=float(accuracy_score(yy, oof >= 0.5)),
        auc=_auc(yy, oof, roc_auc_score),
        folds=out,
        oof_proba=pd.Series(oof, index=X.index, name="p_drug"),
    )


def grouped_cv(X: pd.DataFrame, y: pd.Series, groups: pd.Series, n_splits: int = 5, seed: int = 0) -> tuple[float, float]:
    """Return (accuracy, auc), split by site so the model can't memorize a site."""
    r = cross_validate(X, y, groups, n_splits=n_splits, seed=seed)
    return r.accuracy, r.auc


def _auc(y: np.ndarray, p: np.ndarray, roc_auc_score) -> float:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan")

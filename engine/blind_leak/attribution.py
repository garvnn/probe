"""Leak localization: SHAP + drop-column delta. Owner: Ajay.

SHAP values are TreeSHAP contributions from LightGBM (`pred_contrib=True`), computed out-of-fold on each
site-grouped test fold. Drop-column importance retrains the same CV without a column (or without a whole
field group) and reports the AUC lost. Features within a field group are often correlated, so per-feature
drop deltas understate a group; the group table is the one that maps to a remedy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.blind_leak.classifier import cross_validate, encode_labels, make_model, site_folds
from engine.blind_leak.features import group_of, label_of

OWNER = "Ajay"


def shap_importance(X: pd.DataFrame, y: pd.Series, groups: pd.Series, seed: int = 0, n_splits: int = 5) -> pd.Series:
    """Mean |SHAP| per feature over out-of-fold predictions."""
    yy = encode_labels(y)
    contrib = np.zeros((len(X), X.shape[1]))
    for i, (tr, te) in enumerate(site_folds(groups, n_splits)):
        model = make_model(seed + i)
        model.fit(X.iloc[tr], yy[tr])
        contrib[te] = model.predict(X.iloc[te], pred_contrib=True)[:, :-1]
    return pd.Series(np.abs(contrib).mean(axis=0), index=X.columns, name="shap").sort_values(ascending=False)


def drop_column_auc(X: pd.DataFrame, y: pd.Series, groups: pd.Series, columns: dict[str, list[str]], seed: int = 0) -> pd.Series:
    """AUC drop when each named set of columns is removed and the CV is rerun."""
    folds = site_folds(groups)
    base = cross_validate(X, y, groups, seed=seed, folds=folds).auc
    out = {}
    for name, cols in columns.items():
        rest = X.drop(columns=cols)
        out[name] = base - (cross_validate(rest, y, groups, seed=seed, folds=folds).auc if rest.shape[1] else 0.5)
    return pd.Series(out, name="drop_auc")


def leak_table(
    X: pd.DataFrame, y: pd.Series, groups: pd.Series, seed: int = 0, top: int = 15, shap: pd.Series | None = None
) -> pd.DataFrame:
    """Per-feature table ranked by mean |SHAP|, with drop-column AUC delta for the top features."""
    shap = shap if shap is not None else shap_importance(X, y, groups, seed=seed)
    head = list(shap.index[:top])
    drop = drop_column_auc(X, y, groups, {c: [c] for c in head}, seed=seed)
    t = pd.DataFrame({"field": head, "group": [group_of(c) for c in head], "label": [label_of(c) for c in head],
                      "shap": shap.loc[head].to_numpy(), "drop_auc": drop.loc[head].to_numpy()})
    t.insert(0, "rank", range(1, len(t) + 1))
    return t


def group_table(X: pd.DataFrame, y: pd.Series, groups: pd.Series, seed: int = 0) -> pd.DataFrame:
    """Per field group: summed mean |SHAP| and AUC lost when the whole group is dropped."""
    shap = shap_importance(X, y, groups, seed=seed)
    by_group: dict[str, list[str]] = {}
    for c in X.columns:
        by_group.setdefault(group_of(c), []).append(c)
    drop = drop_column_auc(X, y, groups, by_group, seed=seed)
    t = pd.DataFrame({
        "group": list(by_group),
        "n_features": [len(v) for v in by_group.values()],
        "shap": [float(shap.loc[v].sum()) for v in by_group.values()],
        "drop_auc": [float(drop[k]) for k in by_group],
    }).sort_values(["shap"], ascending=False, kind="stable").reset_index(drop=True)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t


def rank_leaks(X: pd.DataFrame, y: pd.Series, groups: pd.Series, seed: int = 0, top: int = 5) -> list[dict]:
    """Rank fields by how much they reveal the arm. Each entry carries a plain-English label for the UI.

    `importance` is the feature's share of total mean |SHAP|; `drop_auc` is the AUC lost without it.
    """
    shap = shap_importance(X, y, groups, seed=seed)
    t = leak_table(X, y, groups, seed=seed, top=top, shap=shap)
    total = float(shap.sum()) or 1.0
    return [
        {"field": r.field, "label": r.label, "group": r.group, "importance": round(float(r.shap) / total, 4),
         "shap": float(r.shap), "drop_auc": float(r.drop_auc)}
        for r in t.itertuples()
    ]

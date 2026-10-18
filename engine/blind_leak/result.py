"""BlindResult and the run_blind entry point. Owner: Ajay."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from engine.blind_leak.attribution import rank_leaks
from engine.blind_leak.features import build_features, feature_columns
from engine.blind_leak.permutation import DEFAULT_N, run_permutation

OWNER = "Ajay"


@dataclass
class BlindResult:
    """Outcome of one blind-leak run on one view.

    Attributes:
        accuracy: Arm-prediction accuracy, cross-validated grouped by site.
        auc: ROC AUC, same CV.
        null_lo: Lower edge of the permutation-null band (shuffled labels).
        null_hi: Upper edge of the permutation-null band.
        utility: Operational utility retained by the remedies that produced this view (1.0 if none).
        top_leaks: Ranked leaking fields, e.g. [{"field": "unscheduled_visits", "label": "extra unscheduled visits", "importance": ...}].
        p_value: Permutation p-value for the accuracy.
        n_permutations, seed: How the null was drawn.
        folds: Per-fold accuracy/AUC and the sites in each test fold.
    """

    accuracy: float
    auc: float
    null_lo: float
    null_hi: float
    utility: float
    top_leaks: list[dict]
    p_value: float = float("nan")
    p_value_auc: float = float("nan")
    n_permutations: int = 0
    seed: int = 0
    folds: list[dict] = field(default_factory=list)

    @property
    def blind_holds(self) -> bool:
        """Permutation p >= 0.05 and accuracy inside the null's 95% band."""
        return self.p_value >= 0.05 and self.null_lo <= self.accuracy <= self.null_hi


def run_blind(
    view_df: pd.DataFrame,
    trial_id: str,
    labels: pd.Series | None = None,
    n_permutations: int = DEFAULT_N,
    seed: int = 0,
    utility: float = 1.0,
    top: int = 5,
) -> BlindResult:
    """Featurize, classify, permutation-test, and attribute. Ground truth is joined only inside scoring.

    Features are built from the view before any label is touched. `labels` (drug|placebo by
    patient_id) are used only as the classifier target; if omitted they come from evals.scoring.
    """
    feats = build_features(view_df)
    if labels is None:
        from evals.scoring import arm_labels

        labels = arm_labels(trial_id)
    X, y, groups = align(feats, labels)

    perm = run_permutation(X, y, groups, n=n_permutations, seed=seed)
    leaks = rank_leaks(X, y, groups, seed=seed, top=top)
    return BlindResult(
        accuracy=perm.observed.accuracy,
        auc=perm.observed.auc,
        null_lo=perm.null_lo,
        null_hi=perm.null_hi,
        utility=utility,
        top_leaks=leaks,
        p_value=perm.p_value,
        p_value_auc=perm.p_value_auc,
        n_permutations=n_permutations,
        seed=seed,
        folds=[vars(f) for f in perm.observed.folds],
    )


def align(feats: pd.DataFrame, labels: pd.Series) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Inner-join features and labels on patient_id. Returns (X, y, site groups)."""
    common = feats.index.intersection(labels.index)
    if len(common) == 0:
        raise ValueError("no patient_id overlap between view and labels")
    f = feats.loc[common]
    return f[feature_columns(f)].astype(float), labels.loc[common], f["site_id"]

"""Metric names and the one logging entry point everyone uses. Owner: Ajay.

Same numbers feed the UI, Chalk, and the report: one source of truth.
"""

from __future__ import annotations

OWNER = "Ajay"

METRICS = (
    "fraud_evasion_rate",
    "generalization_to_held_out_attack",
    "legitimate_false_positive_rate",
    "damage_effect_shift",
    "unblinding_accuracy",
    "unblinding_auc",
    "permutation_null",
    "operational_utility_retained",
    "integrity_margin",
    "minimum_fix_cost",
)


def log_metric(name: str, value: float, context: dict) -> None:
    """Persist one metric to eval_results and forward it to Chalk. `name` must be in METRICS."""
    raise NotImplementedError(f"owner: {OWNER}")

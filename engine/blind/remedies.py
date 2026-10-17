"""Real-world blinding remedies and their assigned costs. Owner: Ajay."""

from __future__ import annotations

REMEDIES = ["unblinded_pharmacist", "sham_titration", "central_lab", "matched_kits"]

# assigned by us; label as assigned in the UI
REMEDY_COST: dict[str, float] = {
    "sham_titration": 1.0,
    "matched_kits": 1.0,
    "central_lab": 2.0,
    "unblinded_pharmacist": 3.0,
}

REMEDY_FIELDS: dict[str, str] = {
    "unblinded_pharmacist": "Dispensing log removed from coordinator view",
    "sham_titration": "Placebo arm gets matching titration events",
    "central_lab": "Local glucose values removed; efficacy labs masked",
    "matched_kits": "Kit storage / packaging fields normalized",
}
"""What each remedy does to the view. Adverse events are never hidden: that leak is handled by
re-testing the separate blinded outcome-assessor view."""

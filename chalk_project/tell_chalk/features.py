"""Chalk feature definitions for Tell (blind leak): one Patient entity on the coordinator view.

Inputs are export_view() rows only. The treatment arm is never a Chalk feature: Tell joins it locally,
from ground_truth, inside scoring.

`view_rows`   input: this patient's coordinator-view rows as JSON (tell_chalk.vector.rows_to_json)
`tell_vector` the full per-patient feature vector Tell's classifier uses (tell_chalk.vector)
the rest      named, catalog-friendly features read off the same vector
"""

from __future__ import annotations

import json

from chalk.features import Features, features, online

from engine.blind_leak.features import _slug
from tell_chalk.vector import vector_json

AE_CATEGORIES = {
    "GI": "gi",
    "Nervous system": "nervous_system",
    "Infection": "infection",
    "Musculoskeletal": "musculoskeletal",
    "General": "general",
}
"""From docs/schema.md (adverse_events.category)."""


@features
class Patient:
    id: str
    site_id: str
    view_rows: str
    tell_vector: str

    unscheduled_visit_count: int
    ae_count_gi: int
    ae_count_nervous_system: int
    ae_count_infection: int
    ae_count_musculoskeletal: int
    ae_count_general: int
    antiemetic_flag: bool
    dispensing_count: int
    kit_returns: int
    visit_gap_mean: float | None
    visit_gap_std: float | None
    local_glucose_slope: float | None


@online
def compute_tell_vector(view_rows: Patient.view_rows) -> Patient.tell_vector:
    """Per-patient half of engine.blind_leak.features.build_features (see tell_chalk/vector.py)."""
    return vector_json(view_rows)


def named_features(vector: list[list]) -> dict:
    """The catalog features, read from a patient's vector by column name."""
    by_col = {col: value for _, col, value in vector}

    def n(col: str) -> int:
        return int(by_col.get(col) or 0)

    out = {f"ae_count_{slug}": n(f"adverse_events__cat__{_slug(cat)}_n") for cat, slug in AE_CATEGORIES.items()}
    out.update(
        unscheduled_visit_count=n("visits__visit__cat__unscheduled_n"),
        antiemetic_flag=n("conmeds__antiemetic_n") > 0,
        dispensing_count=n("dispensing__rows_n"),
        kit_returns=n("dispensing__return_n"),
        visit_gap_mean=by_col.get("visits__visit__gap_mean"),
        visit_gap_std=by_col.get("visits__visit__gap_std"),
        local_glucose_slope=by_col.get("local_labs__glucose_fingerstick_local__slope"),
    )
    return out


@online
def compute_named_features(
    tell_vector: Patient.tell_vector,
) -> Features[
    Patient.unscheduled_visit_count,
    Patient.ae_count_gi,
    Patient.ae_count_nervous_system,
    Patient.ae_count_infection,
    Patient.ae_count_musculoskeletal,
    Patient.ae_count_general,
    Patient.antiemetic_flag,
    Patient.dispensing_count,
    Patient.kit_returns,
    Patient.visit_gap_mean,
    Patient.visit_gap_std,
    Patient.local_glucose_slope,
]:
    return Patient(**named_features(json.loads(tell_vector)))

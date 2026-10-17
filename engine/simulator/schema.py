"""Machine-readable trial schema. Owner: Garv.

Mirrors docs/schema.md (tests/test_simulator.py checks they agree). Import this instead of
hard-coding column lists: the fake-data validator, the check suite, and the views all read it.
"""

from __future__ import annotations

import pandas as pd

ColumnType = str
"""One of "str", "int", "float", "bool", "date"."""

SCHEMA: dict[str, dict[str, ColumnType]] = {
    "patients": {
        "patient_id": "str",
        "site_id": "str",
        "age": "int",
        "sex": "str",
        "bmi": "float",
        "baseline_hba1c": "float",
    },
    "sites": {
        "site_id": "str",
        "trial_id": "str",
        "is_fake": "bool",
        "source": "str",
    },
    "visits": {
        "visit_id": "str",
        "patient_id": "str",
        "visit_name": "str",
        "date": "date",
        "scheduled": "bool",
    },
    "labs": {
        "lab_id": "str",
        "visit_id": "str",
        "test": "str",
        "value": "float",
        "source": "str",
        "draw_time": "str",
    },
    "vitals": {
        "visit_id": "str",
        "sbp": "int",
        "dbp": "int",
        "weight": "float",
    },
    "adverse_events": {
        "ae_id": "str",
        "patient_id": "str",
        "term": "str",
        "category": "str",
        "onset_date": "date",
        "severity": "str",
    },
    "conmeds": {
        "patient_id": "str",
        "drug_class": "str",
        "start_date": "date",
    },
    "dispensing": {
        "event_id": "str",
        "patient_id": "str",
        "date": "date",
        "kit_id": "str",
        "event_type": "str",
    },
    "kit_storage": {
        "event_id": "str",
        "patient_id": "str",
        "kit_id": "str",
        "date": "date",
        "event_type": "str",
        "storage": "str",
        "temp_c": "float",
    },
}
"""Table -> column -> type for every table a Trial carries. Column order is canonical."""

GROUND_TRUTH_SCHEMA: dict[str, ColumnType] = {"patient_id": "str", "arm": "str"}
"""The locked table. Never part of SCHEMA, never in a Trial, never in a view."""

VIEW_COLUMNS: dict[str, ColumnType] = {
    "patient_id": "str",
    "site_id": "str",
    "source": "str",
    "date": "date",
    "kind": "str",
    "category": "str",
    "value": "float",
    "detail": "str",
}
"""Columns of the long-format frame export_view returns (see docs/schema.md, "Views")."""

VISIT_SCHEDULE: dict[str, int] = {
    "Screening": -14,
    "Baseline": 0,
    "Week 2": 14,
    "Week 4": 28,
    "Week 8": 56,
    "Week 12": 84,
    "Week 16": 112,
    "Week 20": 140,
    "Week 24": 168,
}
"""Scheduled visit name -> target study day relative to baseline. Unscheduled visits are named "Unscheduled"."""


def coerce(columns: dict[str, ColumnType], df: pd.DataFrame) -> pd.DataFrame:
    """Return `df` with exactly `columns`, in order, cast to their schema types.

    Raises KeyError naming any missing columns. Extra columns are dropped.
    """
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"missing columns: {missing}")
    out = df.loc[:, list(columns)].copy()
    for col, kind in columns.items():
        if kind == "date":
            out[col] = pd.to_datetime(out[col]).dt.normalize()
        elif kind == "int":
            out[col] = out[col].astype("int64")
        elif kind == "float":
            out[col] = out[col].astype("float64")
        elif kind == "bool":
            out[col] = out[col].astype(bool)
        else:
            out[col] = out[col].astype(object).where(out[col].notna(), None)
    return out.reset_index(drop=True)


def empty_table(table: str) -> pd.DataFrame:
    """A zero-row DataFrame with `table`'s columns and types."""
    return coerce(SCHEMA[table], pd.DataFrame({c: [] for c in SCHEMA[table]}))

"""Role-filtered exports of a trial. Owner: Garv.

This is the only way the blind-leak attack sees trial data (bias firewall).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from engine.blind_leak.remedies import REMEDIES
from engine.simulator import store
from engine.simulator.schema import VIEW_COLUMNS, coerce

OWNER = "Garv"

Role = Literal["coordinator", "investigator", "pharmacist", "assessor"]

ROLE_GROUPS: dict[str, frozenset[str]] = {
    "coordinator": frozenset({"visits", "adverse_events", "conmeds", "dispensing", "local_labs", "kit_storage"}),
    "investigator": frozenset({"visits", "adverse_events", "conmeds", "local_labs"}),
    "pharmacist": frozenset({"dispensing", "kit_storage"}),
    "assessor": frozenset({"visits", "central_labs"}),
}
"""Role -> visible field groups. Matches the role matrix in docs/schema.md and backend/mocks/trial_detail.json."""


_DEFAULTS: dict[str, object] = {"date": pd.NaT, "value": np.nan}


def _rows(df: pd.DataFrame, source: str, consts: dict[str, object] | None = None, **cols: str) -> pd.DataFrame:
    """Build view rows from `df`. `cols` maps view column -> column of `df`; `consts` sets fixed values."""
    consts = {"source": source, **(consts or {})}
    out = pd.DataFrame(index=df.index)
    for name in VIEW_COLUMNS:
        if name in cols:
            out[name] = df[cols[name]]
        else:
            out[name] = consts.get(name, _DEFAULTS.get(name, ""))
    return out


def _view_parts(tables: dict[str, pd.DataFrame], site_of: pd.Series) -> dict[str, pd.DataFrame]:
    """Field group -> view rows, for every group. Role filtering happens afterwards."""
    visits = tables["visits"].assign(site_id=lambda d: d["patient_id"].map(site_of))
    by_visit = visits.set_index("visit_id")[["patient_id", "site_id", "date"]]

    patients = tables["patients"]
    demo = pd.concat(
        [
            _rows(patients, "patient", {"kind": "age"}, patient_id="patient_id", site_id="site_id", value="age"),
            _rows(patients, "patient", {"kind": "sex"}, patient_id="patient_id", site_id="site_id", category="sex"),
            _rows(patients, "patient", {"kind": "bmi"}, patient_id="patient_id", site_id="site_id", value="bmi"),
        ]
    )

    v = visits.assign(category=np.where(visits["scheduled"], "scheduled", "unscheduled"))
    visit_rows = _rows(v, "visit", patient_id="patient_id", site_id="site_id", date="date", kind="visit_name", category="category", detail="visit_id")
    vit = tables["vitals"].join(by_visit, on="visit_id").melt(
        id_vars=["visit_id", "patient_id", "site_id", "date"], value_vars=["sbp", "dbp", "weight"], var_name="kind", value_name="value"
    )
    vital_rows = _rows(vit, "vital", patient_id="patient_id", site_id="site_id", date="date", kind="kind", value="value", detail="visit_id")

    labs = tables["labs"].join(by_visit, on="visit_id")
    lab_rows = _rows(labs, "lab", patient_id="patient_id", site_id="site_id", date="date", kind="test", category="source", value="value", detail="draw_time")

    ae = tables["adverse_events"].assign(site_id=lambda d: d["patient_id"].map(site_of))
    cm = tables["conmeds"].assign(site_id=lambda d: d["patient_id"].map(site_of))
    kits = tables["kit_storage"].assign(site_id=lambda d: d["patient_id"].map(site_of))
    return {
        "demographics": demo,
        "visits": pd.concat([visit_rows, vital_rows]),
        "local_labs": lab_rows[labs["source"] == "local"],
        "central_labs": lab_rows[labs["source"] == "central"],
        "adverse_events": _rows(ae, "adverse_event", patient_id="patient_id", site_id="site_id", date="onset_date", kind="term", category="category", detail="severity"),
        "conmeds": _rows(cm, "conmed", patient_id="patient_id", site_id="site_id", date="start_date", kind="drug_class"),
        "dispensing": _dispensing_rows(tables["dispensing"], site_of),
        "kit_storage": _rows(kits, "kit_storage", patient_id="patient_id", site_id="site_id", date="date", kind="event_type", category="storage", value="temp_c", detail="kit_id"),
    }


def _dispensing_rows(dispensing: pd.DataFrame, site_of: pd.Series) -> pd.DataFrame:
    d = dispensing.assign(site_id=lambda x: x["patient_id"].map(site_of))
    return _rows(d, "dispensing", patient_id="patient_id", site_id="site_id", date="date", kind="event_type", detail="kit_id")


def export_view(trial_id: str, role: Role, remedies: list[str] = []) -> pd.DataFrame:  # noqa: B006
    """Return the patient-level data `role` is allowed to see, after applying `remedies`.

    Never includes the arm column, or anything derived from ground truth. Remedy names are
    those in `engine.blind_leak.remedies.REMEDIES`; each one removes or normalizes the fields it
    covers (e.g. "central_lab" removes local glucose values).
    """
    if role not in ROLE_GROUPS:
        raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLE_GROUPS)}")
    unknown = sorted(set(remedies) - set(REMEDIES))
    if unknown:
        raise ValueError(f"unknown remedies {unknown}; expected names from REMEDIES: {REMEDIES}")

    tables = store.load_tables(trial_id)
    site_of = tables["patients"].set_index("patient_id")["site_id"]
    parts = _view_parts(tables, site_of)

    groups = set(ROLE_GROUPS[role]) | {"demographics"}
    if "unblinded_pharmacist" in remedies and role != "pharmacist":
        groups.discard("dispensing")
    if "central_lab" in remedies:
        groups.discard("local_labs")
    if "sham_titration" in remedies:
        sham = _dispensing_rows(store.load_hidden(trial_id, "sham_dispensing"), site_of)
        parts["dispensing"] = pd.concat([parts["dispensing"], sham])
    if "matched_kits" in remedies:
        parts["kit_storage"] = parts["kit_storage"].assign(category="matched", value=np.nan)

    frames = [parts[g] for g in sorted(groups) if len(parts[g])]
    view = coerce(VIEW_COLUMNS, pd.concat(frames, ignore_index=True))
    view["date_sort"] = view["date"].fillna(pd.Timestamp.min)
    view = view.sort_values(["patient_id", "date_sort", "source", "kind", "detail"], kind="stable").drop(columns="date_sort")
    return view.reset_index(drop=True)

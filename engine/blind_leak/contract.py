"""The parts of docs/schema.md that Tell depends on, copied by hand. Owner: Ajay.

Bias firewall: these values come from docs/schema.md only, not from engine.simulator. If the schema
doc changes, update this file to match.
"""

from __future__ import annotations

VIEW_COLUMNS = ["patient_id", "site_id", "source", "date", "kind", "category", "value", "detail"]

ROLES = ["coordinator", "investigator", "pharmacist", "assessor"]

FIELD_GROUPS = ["visits", "adverse_events", "conmeds", "dispensing", "local_labs", "central_labs", "kit_storage"]

# "Who sees which field group" matrix from docs/schema.md.
ROLE_GROUPS: dict[str, set[str]] = {
    "coordinator": {"visits", "adverse_events", "conmeds", "dispensing", "local_labs", "kit_storage"},
    "investigator": {"visits", "adverse_events", "conmeds", "local_labs"},
    "pharmacist": {"dispensing", "kit_storage"},
    "assessor": {"visits", "central_labs"},
}

SCHEDULED_VISITS: dict[str, int] = {
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

AE_CATEGORIES = ["GI", "Nervous system", "Infection", "Musculoskeletal", "General"]
AE_SEVERITIES = ["mild", "moderate", "severe"]

# Adverse events are safety information. No remedy may remove or alter these rows in the coordinator view.
SAFETY_SOURCES = {"adverse_event"}


def field_group(source: str, category: str = "") -> str:
    """Map a view row's source (and lab category) to its schema field group. `patient` rows have none."""
    if source in ("visit", "vital"):
        return "visits"
    if source == "lab":
        return "central_labs" if category == "central" else "local_labs"
    return {
        "adverse_event": "adverse_events",
        "conmed": "conmeds",
        "dispensing": "dispensing",
        "kit_storage": "kit_storage",
        "patient": "patient",
    }[source]

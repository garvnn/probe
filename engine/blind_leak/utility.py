"""Declared site-task utility, based only on docs/schema.md. Owner: Ajay.

Fields are role.field_group.view_column. This is an assigned operational model, not
measured staff productivity. Delegating dispensing to the pharmacist preserves that task.
With six equally weighted, all-or-nothing tasks, a 0.90 floor requires all six tasks.
"""
from __future__ import annotations

OWNER = "Ajay"

TASK_FIELDS: dict[str, frozenset[str]] = {
    "schedule_visits": frozenset(f"coordinator.visits.{c}" for c in ("patient_id", "date", "kind")),
    "report_safety_events": frozenset(f"investigator.adverse_events.{c}" for c in
                                     ("patient_id", "site_id", "date", "kind", "category", "detail")),
    "manage_inventory": frozenset({"pharmacist.dispensing.detail", "pharmacist.dispensing.kind",
                                   "pharmacist.kit_storage.detail", "pharmacist.kit_storage.date",
                                   "pharmacist.kit_storage.category", "pharmacist.kit_storage.value"}),
    "track_retention": frozenset(f"coordinator.visits.{c}" for c in ("patient_id", "date", "kind")),
    "query_labs": frozenset(f"investigator.local_labs.{c}" for c in ("patient_id", "date", "kind", "value")),
    "dispense_drug": frozenset(f"pharmacist.dispensing.{c}" for c in ("patient_id", "date", "kind", "detail")),
}
OPERATIONAL_TASKS = list(TASK_FIELDS)

_ROLES = ("coordinator", "investigator", "pharmacist", "assessor")
_COLUMNS = ("patient_id", "site_id", "source", "date", "kind", "category", "value", "detail")
# Removal/masking effects from the public Remedies table in docs/schema.md.
# Investigator AE fields are never removed by any of the four supported remedies.
REMEDY_FIELD_EFFECTS: dict[str, frozenset[str]] = {
    "unblinded_pharmacist": frozenset(f"{r}.dispensing.{c}" for r in _ROLES if r != "pharmacist" for c in _COLUMNS),
    "sham_titration": frozenset(),
    "central_lab": frozenset(f"{r}.local_labs.{c}" for r in _ROLES for c in _COLUMNS),
    "matched_kits": frozenset(f"{r}.kit_storage.{c}" for r in _ROLES for c in ("category", "value")),
}


def _unavailable(remedies: list[str]) -> set[str]:
    unknown = set(remedies) - REMEDY_FIELD_EFFECTS.keys()
    if unknown:
        raise ValueError(f"unknown remedies: {sorted(unknown)}")
    return set().union(*(REMEDY_FIELD_EFFECTS[r] for r in remedies))


def utility(remedies: list[str]) -> float:
    """Fraction of fixed tasks whose required fields remain fully available."""
    unavailable = _unavailable(remedies)
    return sum(not (fields & unavailable) for fields in TASK_FIELDS.values()) / len(TASK_FIELDS)


def safety_accessible(remedies: list[str]) -> bool:
    """Require complete investigator access to AE identity, term, time, category and severity."""
    return not bool(TASK_FIELDS["report_safety_events"] & _unavailable(remedies))

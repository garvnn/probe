"""Operational utility: fraction of required site tasks still fully supported. Owner: Ajay.

The task list and which remedy breaks which task are ASSIGNED by us, like the remedy costs: a documented
rubric, not a measurement. A task counts as supported if some site role can still do it from the data
that role sees under the remedy set. Moving a task to the right person (e.g. dispensing to an unblinded
pharmacist) keeps it supported; a remedy that removes the data everyone needs for a task loses it.
"""

from __future__ import annotations

from engine.blind_leak.remedies import validate

OWNER = "Ajay"

OPERATIONAL_TASKS: dict[str, dict] = {
    "schedule_visits": {"needs": "visits", "lost_under": set()},
    "track_retention": {"needs": "visits", "lost_under": set()},
    "record_adverse_events": {"needs": "adverse_events", "lost_under": set()},
    "report_serious_adverse_events": {"needs": "adverse_events", "lost_under": set()},
    "record_conmeds": {"needs": "conmeds", "lost_under": set()},
    # unblinded_pharmacist moves these three to the pharmacist, who still sees dispensing.
    "dispense_study_drug": {"needs": "dispensing", "lost_under": set()},
    "manage_dose_titration": {"needs": "dispensing", "lost_under": set()},
    "reconcile_kit_returns": {"needs": "dispensing", "lost_under": set()},
    "track_kit_inventory": {"needs": "kit_storage", "lost_under": set()},
    # matched_kits blanks temp_c in every view (docs/schema.md), so no one at the site can check it.
    "check_kit_temperature_on_receipt": {"needs": "kit_storage", "lost_under": {"matched_kits"}},
    # central_lab removes local fingersticks, so the site can't act on a same-day glucose reading.
    "same_day_glucose_safety_check": {"needs": "local_labs", "lost_under": {"central_lab"}},
}

SAFETY_TASKS = {"record_adverse_events", "report_serious_adverse_events"}


def supported_tasks(remedies: list[str]) -> list[str]:
    remedies = set(validate(remedies))
    return [t for t, spec in OPERATIONAL_TASKS.items() if not (spec["lost_under"] & remedies)]


def utility(remedies: list[str]) -> float:
    """Tasks still fully supported under `remedies` / total tasks."""
    return len(supported_tasks(remedies)) / len(OPERATIONAL_TASKS)


def safety_accessible(remedies: list[str]) -> bool:
    """False if any remedy would hide required safety information from the investigator. Never allowed."""
    return SAFETY_TASKS <= set(supported_tasks(remedies))

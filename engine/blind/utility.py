"""Operational utility: fraction of required site tasks still fully supported. Owner: Ajay."""

from __future__ import annotations

OWNER = "Ajay"

OPERATIONAL_TASKS = [
    "schedule_visits",
    "report_safety_events",
    "manage_inventory",
    "track_retention",
    "query_labs",
]


def utility(remedies: list[str]) -> float:
    """Tasks still fully supported under `remedies` / total tasks."""
    raise NotImplementedError(f"owner: {OWNER}")


def safety_accessible(remedies: list[str]) -> bool:
    """False if any remedy would hide required safety information from the investigator. Never allowed."""
    raise NotImplementedError(f"owner: {OWNER}")

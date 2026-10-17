"""Split a Trial into per-site SiteData, the unit every fraud check scores. Owner: Garv (written by Shreyas).

The one site splitter: the Impostor loop, Sentinel scoring, and calibration all use it, so real and
fake sites carry exactly the same tables.
"""

from __future__ import annotations

import pandas as pd

from engine.fraud_checks.base import SiteData
from engine.simulator.schema import SCHEMA
from engine.simulator.trial import Trial

PATIENT_KEYED = ("adverse_events", "conmeds", "dispensing", "kit_storage")
VISIT_KEYED = ("labs", "vitals")
SITE_TABLES = tuple(t for t in SCHEMA if t != "sites")
"""Tables a site (real or fake) carries. `sites` is trial-level metadata, not site data."""


def site_tables(tables: dict[str, pd.DataFrame], site_id: str) -> dict[str, pd.DataFrame]:
    """Every SITE_TABLES table filtered to `site_id`'s patients and their visits."""
    patients = tables["patients"][tables["patients"]["site_id"] == site_id]
    pids = set(patients["patient_id"])
    visits = tables["visits"][tables["visits"]["patient_id"].isin(pids)]
    vids = set(visits["visit_id"])
    out = {"patients": patients.reset_index(drop=True), "visits": visits.reset_index(drop=True)}
    for name in VISIT_KEYED:
        df = tables[name]
        out[name] = df[df["visit_id"].isin(vids)].reset_index(drop=True)
    for name in PATIENT_KEYED:
        df = tables[name]
        out[name] = df[df["patient_id"].isin(pids)].reset_index(drop=True)
    return out


def split_sites(trial: Trial) -> list[SiteData]:
    """One SiteData per real site in the trial, in site_id order."""
    site_ids = sorted(trial.tables["patients"]["site_id"].unique())
    return [SiteData(site_id=s, tables=site_tables(trial.tables, s)) for s in site_ids]

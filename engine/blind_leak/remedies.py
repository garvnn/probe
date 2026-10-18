"""Real-world blinding remedies and their assigned costs. Owner: Ajay.

Effects follow the Remedies table in docs/schema.md. On real data, pass remedy names to
export_view(trial_id, role, remedies=...) so the simulator applies them (sham titration needs records
only the simulator holds). `apply_remedies` is the same transform for synthetic data, and for
re-applying the arm-free remedies to an exported view.

Safety: no remedy removes, hides, or alters adverse-event rows. An AE-driven leak is handled by the
separate blinded outcome assessor, i.e. re-testing role="assessor", never by editing the coordinator view.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REMEDIES = ["unblinded_pharmacist", "sham_titration", "central_lab", "matched_kits"]

# ASSIGNED costs, chosen by us to rank remedies. Not real-world estimates; label as assigned in the UI.
REMEDY_COST: dict[str, float] = {
    "sham_titration": 1.0,
    "matched_kits": 1.0,
    "central_lab": 2.0,
    "unblinded_pharmacist": 3.0,
}
COSTS_ARE_ASSIGNED = True

REMEDY_FIELDS: dict[str, str] = {
    "unblinded_pharmacist": "Dispensing log removed from coordinator view",
    "sham_titration": "Placebo arm gets matching titration events",
    "central_lab": "Local glucose values removed; efficacy labs masked",
    "matched_kits": "Kit storage / packaging fields normalized",
}
"""What each remedy does to the view. Adverse events are never hidden: that leak is handled by
re-testing the separate blinded outcome-assessor view."""

ASSESSOR_REMEDY = "separate_blinded_assessor"
"""Not a view transform. The fix for an AE/safety leak: AEs stay with the coordinator, and the endpoint
is measured by an assessor whose view has no AE rows. Tested by running Tell on role="assessor"."""


def validate(remedies: list[str]) -> list[str]:
    """Raise on unknown names; return the remedies in canonical REMEDIES order."""
    unknown = [r for r in remedies if r not in REMEDIES]
    if unknown:
        raise ValueError(f"unknown remedies {unknown}; known: {REMEDIES}")
    return [r for r in REMEDIES if r in remedies]


def cost(remedies: list[str]) -> float:
    return float(sum(REMEDY_COST[r] for r in validate(remedies)))


def apply_remedies(
    rows: pd.DataFrame,
    remedies: list[str],
    role: str = "coordinator",
    arms: pd.Series | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Apply `remedies` to view rows, then keep what `role` may see."""
    from engine.blind_leak.synthetic import role_filter

    remedies = validate(remedies)
    df = rows.copy()
    if "sham_titration" in remedies:
        if arms is None:
            raise ValueError("sham_titration needs the arm assignment; on real data let export_view apply it")
        df = _sham_titration(df, arms, seed)
    if "unblinded_pharmacist" in remedies and role != "pharmacist":
        df = df.loc[df["source"] != "dispensing"]
    if "central_lab" in remedies:
        df = df.loc[~((df["source"] == "lab") & (df["category"] == "local"))]
    if "matched_kits" in remedies:
        kit = df["source"] == "kit_storage"
        df.loc[kit, "category"] = "matched"
        df.loc[kit, "value"] = np.nan
    df = role_filter(df, role)
    return df.sort_values(["patient_id", "date"], na_position="first", kind="stable").reset_index(drop=True)


def _sham_titration(df: pd.DataFrame, arms: pd.Series, seed: int) -> pd.DataFrame:
    """Each placebo patient gets as many titration_step rows as a randomly matched drug patient at the
    same site, dated on the placebo patient's own dispense dates."""
    rng = np.random.default_rng(seed + 7919)
    disp = df.loc[df["source"] == "dispensing"]
    steps = disp.loc[disp["kind"] == "titration_step"].groupby("patient_id").size()
    dispense_dates = disp.loc[disp["kind"] == "dispense"].groupby("patient_id")["date"].apply(list)
    site_of = df.drop_duplicates("patient_id").set_index("patient_id")["site_id"]
    arm_of = arms.reindex(site_of.index)
    extra = []
    for site, pats in site_of.groupby(site_of):
        ids = list(pats.index)
        drug = [p for p in ids if arm_of.get(p) == "drug"]
        if not drug:
            continue
        for p in ids:
            if arm_of.get(p) != "placebo":
                continue
            n = int(steps.get(drug[int(rng.integers(len(drug)))], 0)) - int(steps.get(p, 0))
            dates = dispense_dates.get(p, [])
            for k in range(max(n, 0)):
                date = dates[min(k + 1, len(dates) - 1)] if dates else pd.NaT
                extra.append((p, site, "dispensing", date, "titration_step", "", np.nan, ""))
    if not extra:
        return df
    return pd.concat([df, pd.DataFrame(extra, columns=df.columns)], ignore_index=True)

"""Documented leak mechanisms that leave operational traces. Owner: Garv.

Each mechanism must have a row in docs/assumptions.md (strength param, default, rationale, source).
No invented correlations.

Every `apply_*` takes the raw tables from `engine.simulator.build._build_raw` (before IDs are assigned)
and mutates them in place. Each gets its own RNG stream, so switching one off leaves the others,
and the base trial, unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.simulator.common import severity, weekday

OWNER = "Garv"

MECHANISMS: dict[str, tuple[float, float]] = {
    "nausea_rr": (1.0, 10.0),
    "titration": (0.0, 1.0),
    "local_glucose": (0.0, 1.0),
    "cold_chain": (0.0, 1.0),
}
"""Config key -> allowed strength range. Keys of TrialConfig.mechanisms must come from here.
nausea_rr: drug/placebo nausea rate ratio. titration: chance a drug patient escalates at each step.
local_glucose: share of the on-treatment glucose change the fingerstick picks up.
cold_chain: share of sites whose placebo kits are logged at room temperature."""

STRENGTH_IF_TRUE: dict[str, float] = {"nausea_rr": 2.5, "titration": 0.6, "local_glucose": 1.0, "cold_chain": 0.3}
"""What `true` means for each key, so configs like {"titration": true} keep working."""

DEFAULT_MECHANISMS: dict[str, object] = {"nausea_rr": 2.5, "titration": True, "local_glucose": True, "cold_chain": True}
"""The demo trial's settings (trial IDs without a suffix, e.g. tr_2026_B)."""

PLACEBO_NAUSEA_P = 0.058
"""Chance a patient reports nausea from background causes over the trial. Matches the background AE
rate in engine/simulator/build.py (AE_RATE x nausea share); tests/test_simulator.py checks that."""
NAUSEA_ONSET_DAYS = (1, 63)
"""Treatment-related nausea starts in the first 9 weeks, around dose escalation."""
NAUSEA_VISIT_P = 0.3
"""Chance a nausea episode brings the patient in for an unscheduled visit. Same in both arms."""
NAUSEA_ANTIEMETIC_P = 0.35
"""Chance a nausea episode gets an antiemetic prescribed. Same in both arms."""

TITRATION_VISITS = ("Week 4", "Week 8")
"""Dose escalation steps on drug."""

AMBIENT_TEMP_C = (21.0, 1.5)
"""Mean and SD of recorded temperature for kits stored at room temperature."""


def strengths(mechanisms: dict) -> dict[str, float]:
    """Resolve a mechanisms config to a strength per key (missing or false -> off).

    Raises ValueError for unknown keys or out-of-range values.
    """
    unknown = sorted(set(mechanisms) - set(MECHANISMS))
    if unknown:
        raise ValueError(f"unknown mechanisms {unknown}; expected keys from {sorted(MECHANISMS)}")
    out: dict[str, float] = {}
    for key, (lo, hi) in MECHANISMS.items():
        value = mechanisms.get(key, False)
        if value is True:
            value = STRENGTH_IF_TRUE[key]
        elif value is False or value is None:
            value = lo
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
            raise ValueError(f"mechanism {key!r} must be true/false or a number in [{lo}, {hi}], got {value!r}")
        out[key] = float(value)
    return out


def validate(mechanisms: dict) -> None:
    """Raise ValueError for unknown mechanism keys or bad values."""
    strengths(mechanisms)


def nausea_followup(
    patient_id: str, onset: pd.Timestamp, last_date: pd.Timestamp, rng: np.random.Generator
) -> tuple[list[dict], list[dict]]:
    """What a nausea episode leaves in the record, whatever its cause: maybe an unscheduled visit,
    maybe an antiemetic. Returns (raw visit rows, raw conmed rows)."""
    visits, conmeds = [], []
    if rng.random() < NAUSEA_VISIT_P:
        date = weekday(onset + pd.Timedelta(days=int(rng.integers(0, 5))), rng)
        if date <= last_date:
            visits.append({"visit_id": None, "patient_id": patient_id, "visit_name": "Unscheduled", "date": date, "scheduled": False, "true_hba1c": np.nan})
    if rng.random() < NAUSEA_ANTIEMETIC_P:
        conmeds.append({"patient_id": patient_id, "drug_class": "antiemetic", "start_date": onset + pd.Timedelta(days=int(rng.integers(0, 3)))})
    return visits, conmeds


def apply_nausea(tables: dict[str, pd.DataFrame], arm: pd.Series, rr: float, rng: np.random.Generator) -> None:
    """Nausea on drug -> unscheduled visits, antiemetic conmeds, AE log entries. Mutates `tables`.

    Drug patients get extra nausea so their overall rate is about `rr` times placebo's. The follow-up
    (visit, antiemetic) uses the same probabilities as background nausea; only the rate differs by arm.
    """
    visits = tables["visits"]
    sched = visits[visits["scheduled"]]
    baseline = sched[sched["visit_name"] == "Baseline"].set_index("patient_id")["date"]
    last = sched.groupby("patient_id")["date"].max()
    p_extra = min(PLACEBO_NAUSEA_P * (rr - 1.0), 0.9)

    new_aes, new_visits, new_meds = [], [], []
    for pid in arm.index[arm == "drug"]:
        if rng.random() >= p_extra:
            continue
        onset = min(baseline[pid] + pd.Timedelta(days=int(rng.integers(*NAUSEA_ONSET_DAYS))), last[pid])
        new_aes.append({"patient_id": pid, "term": "Nausea", "category": "GI", "onset_date": onset, "severity": severity(rng)})
        v, m = nausea_followup(pid, onset, last[pid], rng)
        new_visits.extend(v)
        new_meds.extend(m)

    tables["adverse_events"] = pd.concat([tables["adverse_events"], pd.DataFrame(new_aes)], ignore_index=True)
    tables["visits"] = pd.concat([visits, pd.DataFrame(new_visits, columns=visits.columns)], ignore_index=True)
    tables["conmeds"] = pd.concat([tables["conmeds"], pd.DataFrame(new_meds, columns=tables["conmeds"].columns)], ignore_index=True)


def apply_titration(tables: dict[str, pd.DataFrame], arm: pd.Series, p_step: float, rng: np.random.Generator) -> None:
    """Dose titration on drug (wk 4, 8) -> pharmacy dispensing events. Mutates `tables`.

    At Week 4 each patient escalates with chance `p_step`; at Week 8 again with chance `p_step` if they
    escalated at Week 4 (escalation stops if the last step wasn't tolerated). Drug patients' steps are
    `titration_step` events in dispensing. Placebo patients get the same draw, and their steps go to
    the hidden `sham_dispensing` table, which the sham_titration remedy reveals.
    """
    disp = tables["dispensing"]
    steps = disp[(disp["event_type"] == "dispense") & disp["visit_name"].isin(TITRATION_VISITS)].assign(event_type="titration_step")
    patients = steps["patient_id"].unique()
    first = pd.Series(rng.random(len(patients)) < p_step, index=patients)
    second = first & pd.Series(rng.random(len(patients)) < p_step, index=patients)
    escalates = np.where(steps["visit_name"] == TITRATION_VISITS[0], steps["patient_id"].map(first), steps["patient_id"].map(second))
    steps = steps[escalates.astype(bool)]
    on_drug = steps["patient_id"].map(arm) == "drug"
    tables["dispensing"] = pd.concat([disp, steps[on_drug]], ignore_index=True)
    tables["sham_dispensing"] = pd.concat([tables["sham_dispensing"], steps[~on_drug]], ignore_index=True)


def apply_local_glucose(tables: dict[str, pd.DataFrame], arm: pd.Series, share: float, rng: np.random.Generator) -> None:
    """Drug lowers glucose -> local fingerstick values differ. Mutates `tables`.

    Site fingersticks pick up `share` of each patient's on-treatment HbA1c change (via the ADAG slope)
    instead of staying at baseline. This applies to both arms; the arms only differ where the drug works, so in
    Scenario B it leaks nothing.
    """
    labs = tables["labs"]
    visits = tables["visits"].dropna(subset=["visit_id"]).set_index("visit_id")
    base = tables["patients"].set_index("patient_id")["baseline_hba1c"]
    local = labs["test"] == "glucose_fingerstick"
    vids = labs.loc[local, "visit_id"]
    change = visits.loc[vids, "true_hba1c"].to_numpy() - base[visits.loc[vids, "patient_id"]].to_numpy()
    labs.loc[local, "value"] = np.maximum(np.round(labs.loc[local, "value"].to_numpy() + share * 28.7 * change), 50.0)


def apply_cold_chain(tables: dict[str, pd.DataFrame], arm: pd.Series, site_share: float, rng: np.random.Generator) -> None:
    """Cold-chain drug -> kit storage / temperature log entries. Mutates `tables`.

    Drug kits need refrigeration. At a `site_share` of sites (chosen at random), placebo kits, made
    without the active ingredient, are shipped and logged at room temperature; elsewhere both are
    refrigerated. The matched_kits remedy normalizes these fields.
    """
    kits = tables["kit_storage"]
    site_of = tables["patients"].set_index("patient_id")["site_id"]
    sites = np.array(sorted(site_of.unique()))
    affected = rng.choice(sites, size=int(round(site_share * len(sites))), replace=False)
    placebo = (kits["patient_id"].map(arm) == "placebo") & kits["patient_id"].map(site_of).isin(affected)
    kits.loc[placebo, "storage"] = "ambient"
    kits.loc[placebo, "temp_c"] = np.round(rng.normal(*AMBIENT_TEMP_C, int(placebo.sum())), 1)

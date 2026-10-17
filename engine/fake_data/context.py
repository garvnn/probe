"""What the attacker is allowed to know. Owner: Shreyas.

The attacker plays a site investigator who knows the protocol and the kind of aggregate numbers
published in an investigator brochure or a blinded DSMB summary. It never sees a patient-level row
from another site, and never the treatment arm or anything split by arm.
"""

from __future__ import annotations

import pandas as pd

from engine.fake_data.sites import SITE_TABLES
from engine.simulator.schema import GROUND_TRUTH_SCHEMA, SCHEMA, VISIT_SCHEDULE
from engine.simulator.trial import Trial

OWNER = "Shreyas"

CENTRAL_LAB_VISITS = ["Screening", "Baseline", "Week 12", "Week 24"]
DISPENSE_VISITS = ["Baseline", "Week 4", "Week 8", "Week 12", "Week 16", "Week 20"]


def _summary(x: pd.Series, digits: int = 2) -> dict:
    x = pd.to_numeric(x, errors="coerce").dropna()
    return {
        "mean": round(float(x.mean()), digits),
        "sd": round(float(x.std(ddof=1)), digits),
        "min": round(float(x.min()), digits),
        "max": round(float(x.max()), digits),
    }


def _shares(x: pd.Series) -> dict:
    return {str(k): round(float(v), 3) for k, v in x.value_counts(normalize=True).sort_index().items()}


def public_context(trial: Trial) -> dict:
    """Protocol plus aggregate stats a site investigator could plausibly know.

    Never patient-level rows from other sites, never ground truth, nothing split by arm.
    """
    t = trial.tables
    cfg = trial.config
    patients, visits, labs, vitals = t["patients"], t["visits"], t["labs"], t["vitals"]
    n_patients = len(patients)
    sched = visits[visits["scheduled"]]

    baseline_dates = sched[sched["visit_name"] == "Baseline"]["date"]
    attended = sched.groupby("patient_id")["visit_name"].nunique()
    finished = set(sched[sched["visit_name"] == "Week 24"]["patient_id"])
    labs_by_visit = labs.merge(visits[["visit_id", "visit_name"]], on="visit_id")
    hba1c_bl = labs_by_visit[(labs_by_visit["test"] == "hba1c") & (labs_by_visit["visit_name"] == "Baseline")]
    hba1c_24 = labs_by_visit[(labs_by_visit["test"] == "hba1c") & (labs_by_visit["visit_name"] == "Week 24")]
    pid_of = visits.set_index("visit_id")["patient_id"]
    change = (
        hba1c_24.assign(pid=hba1c_24["visit_id"].map(pid_of)).set_index("pid")["value"]
        - hba1c_bl.assign(pid=hba1c_bl["visit_id"].map(pid_of)).set_index("pid")["value"]
    ).dropna()

    next_site = f"S{cfg.n_sites + 1:02d}"
    return {
        "protocol": {
            "drug": "PRB-101 (fictional), type 2 diabetes",
            "primary_endpoint": "change in central HbA1c (%) from Baseline to Week 24",
            "randomization": "1:1 drug:placebo within each site, permuted blocks of 4",
            "visit_schedule_days": dict(VISIT_SCHEDULE),
            "visit_window_days": 3,
            "central_lab_visits": CENTRAL_LAB_VISITS,
            "central_lab_tests": ["hba1c", "glucose_fasting"],
            "local_lab_tests": ["glucose_fingerstick (every scheduled visit from Baseline)"],
            "dispense_visits": DISPENSE_VISITS,
            "kit_return": "at the next dispensing visit; last return at Week 24",
        },
        "your_site": {
            "site_id": next_site,
            "n_patients": cfg.patients_per_site,
            "first_patient_number": n_patients + 1,
            "patient_id_format": "P followed by the 4-digit patient number",
            "visit_id_format": "V<patient number>-<SCR|BL|W02..W24|U1..>",
            "enrollment_window": [str(baseline_dates.min().date()), str(baseline_dates.max().date())],
        },
        "schema": {
            "tables": {name: dict(SCHEMA[name]) for name in SITE_TABLES},
            "optional_ground_truth": dict(GROUND_TRUTH_SCHEMA),
            "note": "return every table as a list of row dicts; dates as YYYY-MM-DD strings; include ground_truth to say which of your patients are on drug",
        },
        "aggregate_stats": {
            "n_sites": int(cfg.n_sites),
            "patients_per_site": int(cfg.patients_per_site),
            "age": _summary(patients["age"]),
            "sex_share": _shares(patients["sex"]),
            "bmi": _summary(patients["bmi"]),
            "baseline_hba1c": _summary(patients["baseline_hba1c"]),
            "sbp": _summary(vitals["sbp"]),
            "dbp": _summary(vitals["dbp"]),
            "weight": _summary(vitals["weight"]),
            "labs": {test: _summary(g["value"]) for test, g in labs.groupby("test")},
            "hba1c_change_week24_all_patients": _summary(change),
            "draw_time_range": [str(labs["draw_time"].min()), str(labs["draw_time"].max())],
            "kit_temp_c": _summary(t["kit_storage"]["temp_c"]),
        },
        "rates": {
            "scheduled_visits_attended_per_patient": _summary(attended),
            "missed_scheduled_visit_rate": round(float(1 - len(sched) / (n_patients * len(VISIT_SCHEDULE))), 3),
            "completed_week24_share": round(len(finished) / n_patients, 3),
            "unscheduled_visits_per_patient": round(float((~visits["scheduled"]).sum() / n_patients), 3),
            "adverse_events_per_patient": round(len(t["adverse_events"]) / n_patients, 3),
            "adverse_event_terms": _shares(t["adverse_events"]["term"]),
            "adverse_event_severity": _shares(t["adverse_events"]["severity"]),
            "conmed_patient_share": {
                k: round(v / n_patients, 3) for k, v in t["conmeds"].groupby("drug_class")["patient_id"].nunique().items()
            },
        },
    }

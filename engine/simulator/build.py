"""The seeded trial layer: randomization, visits, outcomes, operational records. Owner: Garv.

First-hour version. Shapes, IDs, and the visit/lab/dispensing structure are final; baseline
physiology is drawn from fixed distributions (NHANES comes next) and no leak mechanisms are
applied yet, so nothing a site role can see depends on the arm.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine.simulator.schema import SCHEMA, VISIT_SCHEDULE, coerce, empty_table

TRIAL_START = pd.Timestamp("2026-01-05")
SITE_ACTIVATION_DAYS = 60
"""Sites open over the first two months."""
ENROLLMENT_DAYS = 120
"""Each site enrolls over four months from activation."""
WINDOW_DAYS = 3
P_WEEKEND_MOVED = 0.95
"""Most visits that would land on a weekend get moved to the nearest weekday."""
P_MISSED_VISIT = 0.03
P_DROPOUT = 0.05
UNSCHEDULED_RATE = 0.3
"""Mean unscheduled visits per patient, same in both arms."""
BLOCK_SIZE = 4

PLACEBO_EFFECT = -0.1
DRUG_EFFECT = {"A": -0.6, "B": PLACEBO_EFFECT}
"""Mean HbA1c change at Week 24, percentage points. Simulation parameters, not claims about a drug."""
EFFECT_TAU_WEEKS = 6.0
"""HbA1c moves toward its new level with this time constant."""
SITE_EFFECT_SD = 0.1
PATIENT_RESPONSE_SD = 0.8
HBA1C_ASSAY_SD = 0.15

CENTRAL_LAB_VISITS = ("Screening", "Baseline", "Week 12", "Week 24")
DISPENSE_VISITS = ("Baseline", "Week 4", "Week 8", "Week 12", "Week 16", "Week 20")
FINAL_RETURN_VISIT = "Week 24"

BACKGROUND_AES = (
    ("Headache", "Nervous system", 0.20),
    ("Nasopharyngitis", "Infection", 0.20),
    ("Back pain", "Musculoskeletal", 0.12),
    ("Arthralgia", "Musculoskeletal", 0.10),
    ("Dizziness", "Nervous system", 0.10),
    ("Fatigue", "General", 0.10),
    ("Nausea", "GI", 0.10),
    ("Diarrhoea", "GI", 0.08),
)
"""(term, category, relative frequency). Background rates, same in both arms."""
AE_RATE = 0.6
"""Mean background AEs per patient over the trial."""
BACKGROUND_CONMEDS = (("metformin", 0.9), ("statin", 0.6), ("ace_inhibitor", 0.4))


def _visit_code(name: str) -> str:
    if name == "Screening":
        return "SCR"
    if name == "Baseline":
        return "BL"
    return f"W{int(name.split()[1]):02d}"


def _eag(hba1c: np.ndarray | float) -> np.ndarray | float:
    """Estimated average glucose (mg/dL) from HbA1c (%), ADAG formula."""
    return 28.7 * hba1c - 46.7


def _weekday(date: pd.Timestamp, rng: np.random.Generator) -> pd.Timestamp:
    if date.weekday() >= 5 and rng.random() < P_WEEKEND_MOVED:
        return date + pd.Timedelta(days=-1 if date.weekday() == 5 else 1)
    return date


def _draw_time(rng: np.random.Generator) -> str:
    minutes = 7 * 60 + 30 + 5 * int(rng.integers(0, 43))  # 07:30-11:00
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _patients(n_sites: int, per_site: int, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Patients table plus private per-patient physiology the later steps need."""
    n = n_sites * per_site
    sex = rng.choice(np.array(["F", "M"]), size=n)
    height = np.where(sex == "F", rng.normal(1.62, 0.07, n), rng.normal(1.76, 0.07, n))
    bmi = np.clip(rng.normal(32.0, 6.0, n), 20.0, 50.0).round(1)
    sbp = rng.normal(132.0, 14.0, n)
    patients = pd.DataFrame(
        {
            "patient_id": [f"P{i + 1:04d}" for i in range(n)],
            "site_id": [f"S{i // per_site + 1:02d}" for i in range(n)],
            "age": rng.integers(30, 76, n),
            "sex": sex,
            "bmi": bmi,
            "baseline_hba1c": np.clip(rng.normal(8.3, 0.8, n), 7.0, 10.5).round(1),
        }
    )
    physio = pd.DataFrame(
        {
            "weight": bmi * height**2,
            "sbp": sbp,
            "dbp": 80.0 + 0.5 * (sbp - 132.0) + rng.normal(0.0, 7.0, n),
        },
        index=patients["patient_id"],
    )
    return patients, physio


def _randomize(patients: pd.DataFrame, rng: np.random.Generator) -> pd.Series:
    """1:1 permuted-block randomization within each site."""
    arms: list[str] = []
    for _, site in patients.groupby("site_id", sort=True):
        n = len(site)
        blocks = math.ceil(n / BLOCK_SIZE)
        seq: list[str] = []
        for _ in range(blocks):
            block = ["drug"] * (BLOCK_SIZE // 2) + ["placebo"] * (BLOCK_SIZE // 2)
            seq.extend(rng.permutation(block).tolist())
        arms.extend(seq[:n])
    return pd.Series(arms, index=patients["patient_id"].to_numpy(), name="arm")


def build_tables(
    trial_id: str,
    scenario: str,
    n_sites: int,
    patients_per_site: int,
    rng: np.random.Generator,
) -> tuple[dict[str, pd.DataFrame], pd.Series, dict[str, pd.DataFrame]]:
    """Generate every table for one trial.

    Returns (tables keyed like SCHEMA, arm per patient_id, hidden tables).
    """
    patients, physio = _patients(n_sites, patients_per_site, rng)
    arm = _randomize(patients, rng)

    site_ids = sorted(patients["site_id"].unique())
    site_open = {s: int(rng.integers(0, SITE_ACTIVATION_DAYS + 1)) for s in site_ids}
    site_effect = {s: rng.normal(0.0, SITE_EFFECT_SD) for s in site_ids}
    kit_seq = {s: iter(rng.permutation(np.arange(1, 1000))) for s in site_ids}

    visits, labs, vitals, aes, conmeds, dispensing, kits = [], [], [], [], [], [], []
    scheduled = list(VISIT_SCHEDULE)
    dropout_candidates = scheduled[3:-1]  # Week 2 .. Week 20

    for p in patients.itertuples(index=False):
        pnum = p.patient_id[1:]
        baseline = TRIAL_START + pd.Timedelta(days=site_open[p.site_id] + int(rng.integers(0, ENROLLMENT_DAYS + 1)))
        last_visit = str(rng.choice(dropout_candidates)) if rng.random() < P_DROPOUT else scheduled[-1]
        effect = DRUG_EFFECT[scenario] if arm[p.patient_id] == "drug" else PLACEBO_EFFECT
        response = effect + site_effect[p.site_id] + rng.normal(0.0, PATIENT_RESPONSE_SD)

        attended: list[tuple[str, pd.Timestamp]] = []
        for name in scheduled[: scheduled.index(last_visit) + 1]:
            if name not in ("Screening", "Baseline") and rng.random() < P_MISSED_VISIT:
                continue
            day = VISIT_SCHEDULE[name]
            jitter = 0 if name == "Baseline" else int(rng.integers(-WINDOW_DAYS, WINDOW_DAYS + 1))
            date = baseline + pd.Timedelta(days=day + jitter)
            attended.append((name, date if name == "Baseline" else _weekday(date, rng)))

        for name, date in attended:
            vid = f"V{pnum}-{_visit_code(name)}"
            visits.append({"visit_id": vid, "patient_id": p.patient_id, "visit_name": name, "date": date, "scheduled": True})

            weeks = max((date - baseline).days, 0) / 7.0
            true_hba1c = p.baseline_hba1c + response * (1.0 - math.exp(-weeks / EFFECT_TAU_WEEKS))
            draw_time = _draw_time(rng)
            if name in CENTRAL_LAB_VISITS:
                hba1c = p.baseline_hba1c if name == "Baseline" else true_hba1c + rng.normal(0.0, HBA1C_ASSAY_SD)
                glucose = max(_eag(true_hba1c) + rng.normal(0.0, 18.0), 60.0)
                labs.append({"visit_id": vid, "test": "hba1c", "value": round(hba1c, 1), "source": "central", "draw_time": draw_time})
                labs.append({"visit_id": vid, "test": "glucose_fasting", "value": float(round(glucose)), "source": "central", "draw_time": draw_time})
            if name != "Screening":
                # mechanisms off: fingerstick tracks the patient's baseline, not their on-treatment course
                fingerstick = max(_eag(p.baseline_hba1c) + rng.normal(0.0, 25.0), 50.0)
                labs.append({"visit_id": vid, "test": "glucose_fingerstick", "value": float(round(fingerstick)), "source": "local", "draw_time": draw_time})

            e_sbp = rng.normal(0.0, 8.0)
            phys = physio.loc[p.patient_id]
            vitals.append(
                {
                    "visit_id": vid,
                    "sbp": int(round(phys["sbp"] + e_sbp)),
                    "dbp": int(round(phys["dbp"] + 0.4 * e_sbp + rng.normal(0.0, 5.0))),
                    "weight": round(phys["weight"] + rng.normal(0.0, 0.8), 1),
                }
            )

        first, last = baseline, attended[-1][1]
        span = max((last - first).days, 1)
        offsets = sorted(rng.integers(1, span + 1, int(rng.poisson(UNSCHEDULED_RATE))))
        for k, offset in enumerate(offsets, start=1):
            date = first + pd.Timedelta(days=int(offset))
            visits.append({"visit_id": f"V{pnum}-U{k}", "patient_id": p.patient_id, "visit_name": "Unscheduled", "date": _weekday(date, rng), "scheduled": False})

        terms, cats, freqs = zip(*BACKGROUND_AES)
        probs = np.array(freqs) / sum(freqs)
        for _ in range(int(rng.poisson(AE_RATE))):
            i = int(rng.choice(len(terms), p=probs))
            onset = first + pd.Timedelta(days=int(rng.integers(0, span + 1)))
            severity = str(rng.choice(["mild", "moderate", "severe"], p=[0.7, 0.25, 0.05]))
            aes.append({"patient_id": p.patient_id, "term": terms[i], "category": cats[i], "onset_date": onset, "severity": severity})
            if cats[i] in ("Musculoskeletal", "Nervous system") and rng.random() < 0.5:
                conmeds.append({"patient_id": p.patient_id, "drug_class": "analgesic", "start_date": onset + pd.Timedelta(days=int(rng.integers(0, 3)))})
            if terms[i] == "Nausea" and rng.random() < 0.2:
                conmeds.append({"patient_id": p.patient_id, "drug_class": "antiemetic", "start_date": onset + pd.Timedelta(days=int(rng.integers(0, 3)))})

        screening = attended[0][1]
        for drug_class, prob in BACKGROUND_CONMEDS:
            if rng.random() < prob:
                conmeds.append({"patient_id": p.patient_id, "drug_class": drug_class, "start_date": screening - pd.Timedelta(days=int(rng.integers(180, 2000)))})

        held_kit = None
        for name, date in attended:
            if name not in DISPENSE_VISITS and name != FINAL_RETURN_VISIT:
                continue
            if held_kit is not None:
                dispensing.append({"patient_id": p.patient_id, "date": date, "kit_id": held_kit, "event_type": "return"})
                held_kit = None
            if name in DISPENSE_VISITS:
                kit_id = f"K-{p.site_id[1:]}-{int(next(kit_seq[p.site_id])):03d}"
                received = date - pd.Timedelta(days=int(rng.integers(3, 11)))
                kits.append({"patient_id": p.patient_id, "kit_id": kit_id, "date": received, "event_type": "received", "storage": "refrigerated", "temp_c": round(rng.normal(5.0, 0.8), 1)})
                dispensing.append({"patient_id": p.patient_id, "date": date, "kit_id": kit_id, "event_type": "dispense"})
                held_kit = kit_id

    labs_df = pd.DataFrame(labs)
    labs_df.insert(0, "lab_id", [f"L{i + 1:06d}" for i in range(len(labs_df))])
    aes_df = pd.DataFrame(aes, columns=[c for c in SCHEMA["adverse_events"] if c != "ae_id"])
    aes_df.insert(0, "ae_id", [f"AE{i + 1:05d}" for i in range(len(aes_df))])
    disp_df = pd.DataFrame(dispensing)
    disp_df.insert(0, "event_id", [f"D{i + 1:05d}" for i in range(len(disp_df))])
    kits_df = pd.DataFrame(kits)
    kits_df.insert(0, "event_id", [f"KS{i + 1:05d}" for i in range(len(kits_df))])
    sites = pd.DataFrame({"site_id": site_ids, "trial_id": trial_id, "is_fake": False, "source": "simulator"})

    raw = {
        "patients": patients,
        "sites": sites,
        "visits": pd.DataFrame(visits).sort_values(["patient_id", "date", "visit_id"]),
        "labs": labs_df,
        "vitals": pd.DataFrame(vitals),
        "adverse_events": aes_df,
        "conmeds": pd.DataFrame(conmeds, columns=list(SCHEMA["conmeds"])).sort_values(["patient_id", "start_date"]),
        "dispensing": disp_df,
        "kit_storage": kits_df,
    }
    tables = {name: coerce(SCHEMA[name], df) for name, df in raw.items()}
    hidden = {"sham_dispensing": empty_table("dispensing")}
    return tables, arm, hidden

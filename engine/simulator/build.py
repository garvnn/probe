"""The seeded trial layer: randomization, visits, outcomes, operational records. Owner: Garv.

Three stages: build raw tables from the NHANES base (`_build_raw`), apply the configured leak
mechanisms (engine/simulator/mechanisms.py), then assign IDs and coerce to the schema (`_finalize`).

The base trial draws from one RNG stream and each mechanism from its own, so for a given seed the
trial is identical with mechanisms on or off except for what each mechanism adds or changes.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine.simulator import mechanisms as mech
from engine.simulator.common import eag, severity, weekday
from engine.simulator.nhanes import load_base, sample_patients
from engine.simulator.schema import SCHEMA, VISIT_SCHEDULE, coerce

TRIAL_START = pd.Timestamp("2026-01-05")
SITE_ACTIVATION_DAYS = 60
"""Sites open over the first two months."""
ENROLLMENT_DAYS = 120
"""Each site enrolls over four months from activation."""
WINDOW_DAYS = 3
P_MISSED_VISIT = 0.03
P_DROPOUT = 0.05
UNSCHEDULED_RATE = 0.25
"""Mean unscheduled visits per patient for reasons unrelated to treatment, same in both arms."""
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

MECHANISM_ORDER = ("nausea_rr", "titration", "local_glucose", "cold_chain")
"""Each mechanism's RNG stream is keyed by its position here, so keep the order stable."""


def _visit_code(name: str) -> str:
    if name == "Screening":
        return "SCR"
    if name == "Baseline":
        return "BL"
    return f"W{int(name.split()[1]):02d}"


def _draw_time(rng: np.random.Generator) -> str:
    minutes = 7 * 60 + 30 + 5 * int(rng.integers(0, 43))  # 07:30-11:00
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _patients(n_sites: int, per_site: int, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Patients table plus private per-patient physiology the later steps need."""
    n = n_sites * per_site
    base = sample_patients(load_base(), n, rng)
    ids = [f"P{i + 1:04d}" for i in range(n)]
    patients = pd.DataFrame(
        {
            "patient_id": ids,
            "site_id": [f"S{i // per_site + 1:02d}" for i in range(n)],
            "age": base["age"],
            "sex": base["sex"],
            "bmi": base["bmi"],
            "baseline_hba1c": base["hba1c"],
        }
    )
    physio = base[["weight", "sbp", "dbp"]].set_axis(ids)
    return patients, physio


def _randomize(patients: pd.DataFrame, rng: np.random.Generator) -> pd.Series:
    """1:1 permuted-block randomization within each site."""
    arms: list[str] = []
    for _, site in patients.groupby("site_id", sort=True):
        n = len(site)
        seq: list[str] = []
        for _ in range(math.ceil(n / BLOCK_SIZE)):
            block = ["drug"] * (BLOCK_SIZE // 2) + ["placebo"] * (BLOCK_SIZE // 2)
            seq.extend(rng.permutation(block).tolist())
        arms.extend(seq[:n])
    return pd.Series(arms, index=patients["patient_id"].to_numpy(), name="arm")


def _build_raw(scenario: str, n_sites: int, per_site: int, rng: np.random.Generator) -> tuple[dict[str, pd.DataFrame], pd.Series]:
    """Every table without IDs for unscheduled visits, labs, AEs, and events.

    Raw tables carry helper columns the mechanisms use (`visits.true_hba1c`, `dispensing.visit_name`);
    `_finalize` drops them.
    """
    patients, physio = _patients(n_sites, per_site, rng)
    arm = _randomize(patients, rng)

    site_ids = sorted(patients["site_id"].unique())
    site_open = {s: int(rng.integers(0, SITE_ACTIVATION_DAYS + 1)) for s in site_ids}
    site_effect = {s: rng.normal(0.0, SITE_EFFECT_SD) for s in site_ids}
    kit_seq = {s: iter(rng.permutation(np.arange(1, 1000))) for s in site_ids}

    visits, labs, vitals, aes, conmeds, dispensing, kits = [], [], [], [], [], [], []
    scheduled = list(VISIT_SCHEDULE)
    dropout_candidates = scheduled[3:-1]  # Week 2 .. Week 20
    terms, cats, freqs = zip(*BACKGROUND_AES)
    ae_probs = np.array(freqs) / sum(freqs)

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
            jitter = 0 if name == "Baseline" else int(rng.integers(-WINDOW_DAYS, WINDOW_DAYS + 1))
            date = baseline + pd.Timedelta(days=VISIT_SCHEDULE[name] + jitter)
            attended.append((name, date if name == "Baseline" else weekday(date, rng)))

        phys = physio.loc[p.patient_id]
        for name, date in attended:
            vid = f"V{pnum}-{_visit_code(name)}"
            weeks = max((date - baseline).days, 0) / 7.0
            true_hba1c = p.baseline_hba1c + response * (1.0 - math.exp(-weeks / EFFECT_TAU_WEEKS))
            visits.append({"visit_id": vid, "patient_id": p.patient_id, "visit_name": name, "date": date, "scheduled": True, "true_hba1c": true_hba1c})

            draw_time = _draw_time(rng)
            if name in CENTRAL_LAB_VISITS:
                hba1c = p.baseline_hba1c if name == "Baseline" else true_hba1c + rng.normal(0.0, HBA1C_ASSAY_SD)
                glucose = max(eag(true_hba1c) + rng.normal(0.0, 18.0), 60.0)
                labs.append({"visit_id": vid, "test": "hba1c", "value": round(hba1c, 1), "source": "central", "draw_time": draw_time})
                labs.append({"visit_id": vid, "test": "glucose_fasting", "value": float(round(glucose)), "source": "central", "draw_time": draw_time})
            if name != "Screening":
                # tracks the patient's baseline; mechanisms.apply_local_glucose adds the on-treatment course
                fingerstick = max(eag(p.baseline_hba1c) + rng.normal(0.0, 25.0), 50.0)
                labs.append({"visit_id": vid, "test": "glucose_fingerstick", "value": float(round(fingerstick)), "source": "local", "draw_time": draw_time})

            e_sbp = rng.normal(0.0, 8.0)
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
        for offset in rng.integers(1, span + 1, int(rng.poisson(UNSCHEDULED_RATE))):
            date = weekday(first + pd.Timedelta(days=int(offset)), rng)
            visits.append({"visit_id": None, "patient_id": p.patient_id, "visit_name": "Unscheduled", "date": date, "scheduled": False, "true_hba1c": np.nan})

        for _ in range(int(rng.poisson(AE_RATE))):
            i = int(rng.choice(len(terms), p=ae_probs))
            onset = first + pd.Timedelta(days=int(rng.integers(0, span + 1)))
            aes.append({"patient_id": p.patient_id, "term": terms[i], "category": cats[i], "onset_date": onset, "severity": severity(rng)})
            if terms[i] == "Nausea":
                extra_visits, extra_meds = mech.nausea_followup(p.patient_id, onset, last, rng)
                visits.extend(extra_visits)
                conmeds.extend(extra_meds)
            elif cats[i] in ("Musculoskeletal", "Nervous system") and rng.random() < 0.5:
                conmeds.append({"patient_id": p.patient_id, "drug_class": "analgesic", "start_date": onset + pd.Timedelta(days=int(rng.integers(0, 3)))})

        screening = attended[0][1]
        for drug_class, prob in BACKGROUND_CONMEDS:
            if rng.random() < prob:
                conmeds.append({"patient_id": p.patient_id, "drug_class": drug_class, "start_date": screening - pd.Timedelta(days=int(rng.integers(180, 2000)))})

        held_kit = None
        for name, date in attended:
            if name not in DISPENSE_VISITS and name != FINAL_RETURN_VISIT:
                continue
            if held_kit is not None:
                dispensing.append({"patient_id": p.patient_id, "date": date, "kit_id": held_kit, "event_type": "return", "visit_name": name})
                held_kit = None
            if name in DISPENSE_VISITS:
                kit_id = f"K-{p.site_id[1:]}-{int(next(kit_seq[p.site_id])):03d}"
                received = date - pd.Timedelta(days=int(rng.integers(3, 11)))
                kits.append({"patient_id": p.patient_id, "kit_id": kit_id, "date": received, "event_type": "received", "storage": "refrigerated", "temp_c": round(rng.normal(5.0, 0.8), 1)})
                dispensing.append({"patient_id": p.patient_id, "date": date, "kit_id": kit_id, "event_type": "dispense", "visit_name": name})
                held_kit = kit_id

    disp_cols = list(SCHEMA["dispensing"]) + ["visit_name"]
    raw = {
        "patients": patients,
        "physio": physio,
        "visits": pd.DataFrame(visits),
        "labs": pd.DataFrame(labs),
        "vitals": pd.DataFrame(vitals),
        "adverse_events": pd.DataFrame(aes, columns=[c for c in SCHEMA["adverse_events"] if c != "ae_id"]),
        "conmeds": pd.DataFrame(conmeds, columns=list(SCHEMA["conmeds"])),
        "dispensing": pd.DataFrame(dispensing).reindex(columns=disp_cols),
        "kit_storage": pd.DataFrame(kits),
        "sham_dispensing": pd.DataFrame(columns=disp_cols),
    }
    return raw, arm


def _apply_mechanisms(raw: dict[str, pd.DataFrame], arm: pd.Series, mechanisms: dict, seed: int) -> None:
    strength = mech.strengths(mechanisms)
    apply = {
        "nausea_rr": (mech.apply_nausea, 1.0),
        "titration": (mech.apply_titration, 0.0),
        "local_glucose": (mech.apply_local_glucose, 0.0),
        "cold_chain": (mech.apply_cold_chain, 0.0),
    }
    for i, name in enumerate(MECHANISM_ORDER):
        fn, off = apply[name]
        if strength[name] > off:
            fn(raw, arm, strength[name], np.random.default_rng([seed, i + 1]))


def _with_ids(df: pd.DataFrame, col: str, prefix: str, width: int) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df[col] = [f"{prefix}{i + 1:0{width}d}" for i in range(len(df))]
    return df


def _finalize(raw: dict[str, pd.DataFrame], trial_id: str) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Assign IDs, sort, drop helper columns, and coerce every table to SCHEMA."""
    visits = raw["visits"].sort_values(["patient_id", "date", "scheduled"], ascending=[True, True, False], kind="stable")
    unsched = visits["visit_id"].isna()
    k = visits[unsched].groupby("patient_id").cumcount() + 1
    visits.loc[unsched, "visit_id"] = "V" + visits.loc[unsched, "patient_id"].str[1:] + "-U" + k.astype(str)

    labs = raw["labs"].merge(visits[["visit_id", "patient_id", "date"]], on="visit_id")
    labs = _with_ids(labs.sort_values(["patient_id", "date", "test"], kind="stable"), "lab_id", "L", 6)
    aes = _with_ids(raw["adverse_events"].sort_values(["patient_id", "onset_date", "term"], kind="stable"), "ae_id", "AE", 5)
    order = {"return": 0, "dispense": 1, "titration_step": 2}

    def events(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        df = df.assign(_o=df["event_type"].map(order)).sort_values(["patient_id", "date", "_o"], kind="stable")
        return _with_ids(df, "event_id", prefix, 5)

    sites = pd.DataFrame({"site_id": sorted(raw["patients"]["site_id"].unique()), "trial_id": trial_id, "is_fake": False, "source": "simulator"})
    out = {
        "patients": raw["patients"],
        "sites": sites,
        "visits": visits,
        "labs": labs,
        "vitals": raw["vitals"],
        "adverse_events": aes,
        "conmeds": raw["conmeds"].sort_values(["patient_id", "start_date", "drug_class"], kind="stable"),
        "dispensing": events(raw["dispensing"], "D"),
        "kit_storage": _with_ids(raw["kit_storage"].sort_values(["patient_id", "date"], kind="stable"), "event_id", "KS", 5),
    }
    tables = {name: coerce(SCHEMA[name], df) for name, df in out.items()}
    hidden = {"sham_dispensing": coerce(SCHEMA["dispensing"], events(raw["sham_dispensing"], "SD"))}
    return tables, hidden


def build_tables(
    trial_id: str,
    scenario: str,
    n_sites: int,
    patients_per_site: int,
    seed: int,
    mechanisms: dict,
) -> tuple[dict[str, pd.DataFrame], pd.Series, dict[str, pd.DataFrame]]:
    """Generate every table for one trial.

    Returns (tables keyed like SCHEMA, arm per patient_id, hidden tables).
    """
    raw, arm = _build_raw(scenario, n_sites, patients_per_site, np.random.default_rng(seed))
    _apply_mechanisms(raw, arm, mechanisms, seed)
    tables, hidden = _finalize(raw, trial_id)
    return tables, arm, hidden

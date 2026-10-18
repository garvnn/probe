"""Synthetic trial views for developing and unit-testing Tell and Seal. Owner: Ajay.

Built from docs/schema.md alone (columns, visit schedule, field groups). It does not model the
simulator: by default both arms are drawn from the same distributions, so the blind holds. Leaks are
added explicitly with `Leak` specs, which can target any (source, kind, category) in the view. Never
use this for a reported number; real results come from export_view().
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.blind_leak.contract import ROLE_GROUPS, SCHEDULED_VISITS, VIEW_COLUMNS, field_group

DISPENSING_VISITS = ["Baseline", "Week 4", "Week 8", "Week 12", "Week 16", "Week 20"]
CENTRAL_LAB_VISITS = ["Screening", "Baseline", "Week 12", "Week 24"]
AE_TERMS = [
    ("Headache", "Nervous system"),
    ("Dizziness", "Nervous system"),
    ("Nausea", "GI"),
    ("Diarrhoea", "GI"),
    ("Nasopharyngitis", "Infection"),
    ("Back pain", "Musculoskeletal"),
    ("Arthralgia", "Musculoskeletal"),
    ("Fatigue", "General"),
]
CONMEDS = [("metformin", 0.85), ("statin", 0.55), ("ace_inhibitor", 0.35), ("analgesic", 0.15)]


@dataclass(frozen=True)
class Leak:
    """One injected, arm-dependent difference.

    mode:
        "rate": patients in `arm` get Poisson(`strength`) extra rows of (source, kind, category).
        "shift": rows of (source, kind[, category]) for patients in `arm` get `strength` added to value.
        "category": rows of (source, kind) for patients in `arm` get category `to` (and value `value`
            if given) with probability `strength`, decided per site share `site_share` of sites.
    """

    source: str
    kind: str
    mode: str = "rate"
    strength: float = 1.0
    category: str = ""
    arm: str = "drug"
    to: str = ""
    value: float | None = None
    site_share: float = 1.0


@dataclass
class SyntheticTrial:
    rows: pd.DataFrame
    """Every row any role could see, before role filtering."""
    arms: pd.Series
    """drug | placebo per patient_id. Stands in for ground_truth(); never a feature."""
    seed: int
    leaks: list[Leak] = field(default_factory=list)

    def view(self, role: str = "coordinator", remedies: list[str] | tuple[str, ...] = ()) -> pd.DataFrame:
        """Same contract as export_view(trial_id, role, remedies)."""
        from engine.blind_leak.remedies import apply_remedies

        return apply_remedies(self.rows, list(remedies), role=role, arms=self.arms, seed=self.seed)


def role_filter(rows: pd.DataFrame, role: str) -> pd.DataFrame:
    """Keep the rows `role` may see, per the field-group matrix in docs/schema.md."""
    allowed = ROLE_GROUPS[role] | {"patient"}
    groups = [field_group(s, c) for s, c in zip(rows["source"], rows["category"])]
    keep = np.array([g in allowed for g in groups], dtype=bool)
    return rows.loc[keep]


def make_trial(
    n_sites: int = 20,
    patients_per_site: int = 40,
    leaks: list[Leak] | tuple[Leak, ...] = (),
    seed: int = 0,
) -> SyntheticTrial:
    rng = np.random.default_rng(seed)
    rows: list[tuple] = []
    arms: dict[str, str] = {}
    start = pd.Timestamp("2026-01-05")

    pid = 0
    for s in range(1, n_sites + 1):
        site_id = f"S{s:02d}"
        site_arms = _permuted_blocks(patients_per_site, rng)
        for arm in site_arms:
            pid += 1
            patient_id = f"P{pid:04d}"
            arms[patient_id] = arm
            baseline = start + pd.Timedelta(days=int(rng.integers(0, 180)))
            rows.extend(_patient_rows(patient_id, site_id, pid, baseline, rng))

    df = pd.DataFrame(rows, columns=VIEW_COLUMNS)
    arm_series = pd.Series(arms, name="arm")
    arm_series.index.name = "patient_id"
    for leak in leaks:
        df = _inject(df, arm_series, leak, rng)
    df = _sort(df)
    return SyntheticTrial(rows=df, arms=arm_series, seed=seed, leaks=list(leaks))


def _permuted_blocks(n: int, rng: np.random.Generator) -> list[str]:
    out: list[str] = []
    while len(out) < n:
        out.extend(rng.permutation(["drug", "drug", "placebo", "placebo"]).tolist())
    return out[:n]


def _patient_rows(patient_id: str, site_id: str, pnum: int, baseline: pd.Timestamp, rng: np.random.Generator) -> list[tuple]:
    r: list[tuple] = []
    nan = float("nan")
    age = int(rng.integers(30, 76))
    sex = "F" if rng.random() < 0.5 else "M"
    bmi = round(float(rng.normal(32, 5)), 1)
    r += [
        (patient_id, site_id, "patient", pd.NaT, "age", "", float(age), ""),
        (patient_id, site_id, "patient", pd.NaT, "sex", sex, nan, ""),
        (patient_id, site_id, "patient", pd.NaT, "bmi", "", bmi, ""),
    ]

    hba1c0 = float(rng.normal(8.3, 0.8))
    sbp0, dbp0, wt0 = rng.normal(132, 14), rng.normal(80, 9), rng.normal(92, 16)
    dropout_after = rng.integers(2, 9) if rng.random() < 0.05 else 99
    code = {"Screening": "SCR", "Baseline": "BL"}

    attended: list[tuple[str, pd.Timestamp]] = []
    for i, (name, day) in enumerate(SCHEDULED_VISITS.items()):
        if i > dropout_after:
            break
        if day > 0 and rng.random() < 0.03:
            continue
        date = baseline + pd.Timedelta(days=day + int(rng.integers(-3, 4)))
        visit_id = f"V{pnum:04d}-{code.get(name, 'W' + name.split()[-1].zfill(2))}"
        attended.append((name, date))
        r.append((patient_id, site_id, "visit", date, name, "scheduled", nan, visit_id))
        r += [
            (patient_id, site_id, "vital", date, "sbp", "", float(round(sbp0 + rng.normal(0, 8))), visit_id),
            (patient_id, site_id, "vital", date, "dbp", "", float(round(dbp0 + rng.normal(0, 5))), visit_id),
            (patient_id, site_id, "vital", date, "weight", "", round(float(wt0 + rng.normal(0, 1.5)), 1), visit_id),
        ]
        draw = f"{int(rng.integers(7, 11)):02d}:{int(rng.integers(0, 60)):02d}"
        if name in CENTRAL_LAB_VISITS:
            r.append((patient_id, site_id, "lab", date, "hba1c", "central", round(hba1c0 + rng.normal(0, 0.15), 1), draw))
            glu = 28.7 * hba1c0 - 46.7 + rng.normal(0, 15)
            r.append((patient_id, site_id, "lab", date, "glucose_fasting", "central", float(round(glu)), draw))
        if day >= 0:
            fs = 28.7 * hba1c0 - 46.7 + rng.normal(0, 25)
            r.append((patient_id, site_id, "lab", date, "glucose_fingerstick", "local", float(round(fs)), draw))

    last = attended[-1][1] if attended else baseline
    span = max((last - baseline).days, 1)

    for u in range(rng.poisson(0.25)):
        date = baseline + pd.Timedelta(days=int(rng.integers(1, span + 1)))
        r.append((patient_id, site_id, "visit", date, "Unscheduled", "unscheduled", nan, f"V{pnum:04d}-U{u + 1}"))

    for _ in range(rng.poisson(0.6)):
        term, cat = AE_TERMS[int(rng.integers(len(AE_TERMS)))]
        date = baseline + pd.Timedelta(days=int(rng.integers(1, span + 1)))
        sev = rng.choice(["mild", "moderate", "severe"], p=[0.7, 0.25, 0.05])
        r.append((patient_id, site_id, "adverse_event", date, term, cat, nan, str(sev)))

    for drug_class, p in CONMEDS:
        if rng.random() < p:
            date = baseline - pd.Timedelta(days=int(rng.integers(30, 2000)))
            r.append((patient_id, site_id, "conmed", date, drug_class, "", nan, ""))

    site_num = site_id[1:]
    dispensed = [(n, d) for n, d in attended if n in DISPENSING_VISITS]
    for k, (name, date) in enumerate(dispensed):
        kit = f"K-{site_num}-{pnum:04d}{k:02d}"
        r.append((patient_id, site_id, "kit_storage", date - pd.Timedelta(days=int(rng.integers(3, 15))), "received",
                  "refrigerated", round(float(rng.normal(5, 0.8)), 1), kit))
        r.append((patient_id, site_id, "dispensing", date, "dispense", "", nan, kit))
    for k, (name, date) in enumerate(dispensed):
        nxt = [d for n, d in attended if SCHEDULED_VISITS[n] > SCHEDULED_VISITS[name]]
        if nxt:
            r.append((patient_id, site_id, "dispensing", nxt[0], "return", "", nan, f"K-{site_num}-{pnum:04d}{k:02d}"))
    return r


def _inject(df: pd.DataFrame, arms: pd.Series, leak: Leak, rng: np.random.Generator) -> pd.DataFrame:
    arm_of = df["patient_id"].map(arms)
    sites = sorted(df["site_id"].unique())
    leak_sites = set(rng.choice(sites, size=max(1, round(leak.site_share * len(sites))), replace=False))
    in_scope = (arm_of == leak.arm) & df["site_id"].isin(leak_sites)

    if leak.mode == "rate":
        pats = df.loc[in_scope & (df["source"] == "visit")].groupby("patient_id")["date"].agg(["min", "max"])
        site_of = df.drop_duplicates("patient_id").set_index("patient_id")["site_id"]
        extra = []
        for patient_id, span in pats.iterrows():
            for _ in range(rng.poisson(leak.strength)):
                days = max((span["max"] - span["min"]).days, 1)
                date = span["min"] + pd.Timedelta(days=int(rng.integers(0, days + 1)))
                value = float(leak.value) if leak.value is not None else float("nan")
                detail = "mild" if leak.source == "adverse_event" else ""
                extra.append((patient_id, site_of[patient_id], leak.source, date, leak.kind, leak.category, value, detail))
        return pd.concat([df, pd.DataFrame(extra, columns=VIEW_COLUMNS)], ignore_index=True)

    match = in_scope & (df["source"] == leak.source) & (df["kind"] == leak.kind)
    if leak.category:
        match &= df["category"] == leak.category
    df = df.copy()
    if leak.mode == "shift":
        df.loc[match, "value"] = df.loc[match, "value"] + leak.strength
    elif leak.mode == "category":
        hit = match & (rng.random(len(df)) < leak.strength)
        df.loc[hit, "category"] = leak.to
        if leak.value is not None:
            df.loc[hit, "value"] = leak.value + rng.normal(0, 0.8, int(hit.sum())).round(1)
    else:
        raise ValueError(f"unknown leak mode {leak.mode!r}")
    return df


def _sort(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["patient_id", "date"], na_position="first", kind="stable").reset_index(drop=True)

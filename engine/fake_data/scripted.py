"""TEMPORARY scripted attacker: four hand-written fake-site generators, no LLM. Owner: Shreyas.

Used when no LLM key is set, so the loop, the sandbox, and the UI can be built and demoed now.
Its runs are labeled "scripted" everywhere and are never results. Round N (1-based) returns
version min(N, 4):

    v1  rounded values, too little variance, every visit attended, no adverse events
    v2  realistic noise and spread (SBP and DBP drawn independently)
    v3  preserves correlations: SBP-DBP, and glucose tracks HbA1c
    v4  realistic missingness (missed visits, dropouts, unscheduled visits) and adverse events

Each version is the same template with different knobs, so the code diff between rounds shows
exactly what the attacker "learned". The source is still only ever run in a sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from integrations.llm import LLMCall

OWNER = "Shreyas"
SCRIPTED = True

KNOBS = {
    1: {"ROUND_VALUES": True, "REALISTIC_SPREAD": False, "PRESERVE_CORRELATIONS": False, "REALISTIC_MISSINGNESS": False, "ADVERSE_EVENTS": False},
    2: {"ROUND_VALUES": False, "REALISTIC_SPREAD": True, "PRESERVE_CORRELATIONS": False, "REALISTIC_MISSINGNESS": False, "ADVERSE_EVENTS": False},
    3: {"ROUND_VALUES": False, "REALISTIC_SPREAD": True, "PRESERVE_CORRELATIONS": True, "REALISTIC_MISSINGNESS": False, "ADVERSE_EVENTS": False},
    4: {"ROUND_VALUES": False, "REALISTIC_SPREAD": True, "PRESERVE_CORRELATIONS": True, "REALISTIC_MISSINGNESS": True, "ADVERSE_EVENTS": True},
}

TEMPLATE = '''\
"""Scripted attacker v{version} (TEMPORARY stand-in, not an LLM). Fabricates one site."""
import datetime as dt

import numpy as np

ROUND_VALUES = {ROUND_VALUES}
REALISTIC_SPREAD = {REALISTIC_SPREAD}
PRESERVE_CORRELATIONS = {PRESERVE_CORRELATIONS}
REALISTIC_MISSINGNESS = {REALISTIC_MISSINGNESS}
ADVERSE_EVENTS = {ADVERSE_EVENTS}

DRUG_HBA1C_CHANGE = -1.2   # the effect this attacker wants the drug to show
PLACEBO_HBA1C_CHANGE = -0.1


def generate_site(context):
    rng = np.random.default_rng(context.get("seed", 0))
    proto, site, stats, rates = context["protocol"], context["your_site"], context["aggregate_stats"], context["rates"]
    schedule = proto["visit_schedule_days"]
    n, first = site["n_patients"], site["first_patient_number"]
    lo, hi = (dt.date.fromisoformat(d) for d in site["enrollment_window"])
    spread = 1.0 if REALISTIC_SPREAD else 0.2

    def draw(name, size, digits=1):
        s = stats[name]
        x = np.clip(rng.normal(s["mean"], s["sd"] * spread, size), s["min"], s["max"])
        return np.round(x) if ROUND_VALUES else np.round(x, digits)

    arms = rng.permutation(["drug", "placebo"] * (n // 2) + ["drug"] * (n % 2))
    sexes = rng.choice(list(stats["sex_share"]), size=n, p=list(stats["sex_share"].values()))
    ages, bmis, hba1cs = draw("age", n, 0).astype(int), draw("bmi", n), np.clip(draw("baseline_hba1c", n), 7.0, 10.5)
    sbp_p = rng.normal(stats["sbp"]["mean"], stats["sbp"]["sd"] * 0.85 * spread, n)
    dbp_sd = stats["dbp"]["sd"] * spread
    if PRESERVE_CORRELATIONS:
        dbp_p = stats["dbp"]["mean"] + 0.5 * (sbp_p - stats["sbp"]["mean"]) + rng.normal(0, dbp_sd * 0.7, n)
    else:
        dbp_p = rng.normal(stats["dbp"]["mean"], dbp_sd * 0.85, n)
    weight_p = rng.normal(stats["weight"]["mean"], stats["weight"]["sd"] * spread, n)

    out = {{k: [] for k in ["patients", "visits", "labs", "vitals", "adverse_events", "conmeds", "dispensing", "kit_storage", "ground_truth"]}}
    ids = {{"lab": 0, "ae": 0, "disp": 0, "kit": 0}}
    names = list(schedule)
    p_drop = 1 - rates["completed_week24_share"]

    for i in range(n):
        num = first + i
        pid = f"P{{num:04d}}"
        out["patients"].append({{"patient_id": pid, "site_id": site["site_id"], "age": int(ages[i]), "sex": str(sexes[i]),
                                "bmi": float(bmis[i]), "baseline_hba1c": float(round(hba1cs[i], 1))}})
        out["ground_truth"].append({{"patient_id": pid, "arm": str(arms[i])}})
        baseline = lo + dt.timedelta(days=int(rng.integers(0, (hi - lo).days + 1)))
        change = DRUG_HBA1C_CHANGE if arms[i] == "drug" else PLACEBO_HBA1C_CHANGE
        last = names[-1]
        if REALISTIC_MISSINGNESS and rng.random() < p_drop:
            last = str(rng.choice(names[3:-1]))

        attended = []
        for name in names[: names.index(last) + 1]:
            if REALISTIC_MISSINGNESS and name not in ("Screening", "Baseline") and rng.random() < 0.03:
                continue
            jitter = 0 if (name == "Baseline" or not REALISTIC_SPREAD) else int(rng.integers(-3, 4))
            attended.append((name, baseline + dt.timedelta(days=schedule[name] + jitter)))

        kit = None
        for name, date in attended:
            code = {{"Screening": "SCR", "Baseline": "BL"}}.get(name) or f"W{{int(name.split()[1]):02d}}"
            vid = f"V{{num:04d}}-{{code}}"
            out["visits"].append({{"visit_id": vid, "patient_id": pid, "visit_name": name, "date": date.isoformat(), "scheduled": True}})
            e = rng.normal(0, stats["sbp"]["sd"] * 0.5 * spread)
            sbp = sbp_p[i] + e
            dbp = dbp_p[i] + (0.4 * e if PRESERVE_CORRELATIONS else rng.normal(0, dbp_sd * 0.5)) + rng.normal(0, 5 * spread)
            if ROUND_VALUES:
                sbp, dbp = round(sbp / 10) * 10, round(dbp / 10) * 10
            out["vitals"].append({{"visit_id": vid, "sbp": int(round(sbp)), "dbp": int(round(dbp)),
                                  "weight": float(round(weight_p[i] + rng.normal(0, 0.8 * spread), 1))}})

            weeks = max((date - baseline).days, 0) / 7
            true_hba1c = hba1cs[i] + change * (1 - np.exp(-weeks / 6))
            draw_time = "08:00" if ROUND_VALUES else f"{{7 + int(rng.integers(0, 4)):02d}}:{{5 * int(rng.integers(0, 12)):02d}}"
            if name in proto["central_lab_visits"]:
                hba1c = hba1cs[i] if name == "Baseline" else true_hba1c + rng.normal(0, 0.15 * spread)
                if PRESERVE_CORRELATIONS:
                    glucose = 28.7 * true_hba1c - 46.7 + rng.normal(0, 18)
                else:
                    glucose = rng.normal(stats["labs"]["glucose_fasting"]["mean"], stats["labs"]["glucose_fasting"]["sd"] * spread)
                for test, value in (("hba1c", round(float(hba1c), 1)), ("glucose_fasting", float(round(glucose)))):
                    ids["lab"] += 1
                    out["labs"].append({{"lab_id": f"LF{{num:04d}}{{ids['lab']:05d}}", "visit_id": vid, "test": test, "value": value, "source": "central", "draw_time": draw_time}})
            if name != "Screening":
                ids["lab"] += 1
                fs = stats["labs"]["glucose_fingerstick"]
                out["labs"].append({{"lab_id": f"LF{{num:04d}}{{ids['lab']:05d}}", "visit_id": vid, "test": "glucose_fingerstick",
                                    "value": float(round(rng.normal(fs["mean"], fs["sd"] * spread))), "source": "local", "draw_time": draw_time}})

            if name in proto["dispense_visits"] or name == "Week 24":
                if kit:
                    ids["disp"] += 1
                    out["dispensing"].append({{"event_id": f"DF{{num:04d}}{{ids['disp']:03d}}", "patient_id": pid, "date": date.isoformat(), "kit_id": kit, "event_type": "return"}})
                    kit = None
                if name in proto["dispense_visits"]:
                    ids["kit"] += 1
                    kit = f"K-{{site['site_id'][1:]}}-{{num % 1000:03d}}{{ids['kit']:02d}}"
                    received = date - dt.timedelta(days=int(rng.integers(3, 11)) if REALISTIC_SPREAD else 7)
                    temp = 5.0 if ROUND_VALUES else float(round(rng.normal(stats["kit_temp_c"]["mean"], stats["kit_temp_c"]["sd"]), 1))
                    out["kit_storage"].append({{"event_id": f"KF{{num:04d}}{{ids['kit']:02d}}", "patient_id": pid, "kit_id": kit, "date": received.isoformat(),
                                               "event_type": "received", "storage": "refrigerated", "temp_c": temp}})
                    ids["disp"] += 1
                    out["dispensing"].append({{"event_id": f"DF{{num:04d}}{{ids['disp']:03d}}", "patient_id": pid, "date": date.isoformat(), "kit_id": kit, "event_type": "dispense"}})

        start, end = attended[0][1], attended[-1][1]
        if REALISTIC_MISSINGNESS:
            for k in range(1, int(rng.poisson(rates["unscheduled_visits_per_patient"])) + 1):
                day = start + dt.timedelta(days=int(rng.integers(14, max((end - start).days, 15) + 1)))
                out["visits"].append({{"visit_id": f"V{{num:04d}}-U{{k}}", "patient_id": pid, "visit_name": "Unscheduled", "date": day.isoformat(), "scheduled": False}})
        if ADVERSE_EVENTS:
            terms, sev = rates["adverse_event_terms"], rates["adverse_event_severity"]
            for _ in range(int(rng.poisson(rates["adverse_events_per_patient"]))):
                ids["ae"] += 1
                onset = start + dt.timedelta(days=int(rng.integers(0, max((end - start).days, 1) + 1)))
                term = str(rng.choice(list(terms), p=np.array(list(terms.values())) / sum(terms.values())))
                category = {{"Nausea": "GI", "Diarrhoea": "GI", "Headache": "Nervous system", "Dizziness": "Nervous system",
                            "Nasopharyngitis": "Infection", "Back pain": "Musculoskeletal", "Arthralgia": "Musculoskeletal"}}.get(term, "General")
                out["adverse_events"].append({{"ae_id": f"AEF{{num:04d}}{{ids['ae']:02d}}", "patient_id": pid, "term": term, "category": category,
                                             "onset_date": onset.isoformat(), "severity": str(rng.choice(list(sev), p=np.array(list(sev.values())) / sum(sev.values())))}})
            for drug_class, share in rates["conmed_patient_share"].items():
                if drug_class in ("metformin", "statin", "ace_inhibitor") and rng.random() < share:
                    out["conmeds"].append({{"patient_id": pid, "drug_class": drug_class, "start_date": (start - dt.timedelta(days=int(rng.integers(180, 2000)))).isoformat()}})
    return out
'''


def scripted_source(version: int) -> str:
    """Source for scripted generator `version` (1-4)."""
    return TEMPLATE.format(version=version, **KNOBS[version])


@dataclass
class ScriptedAttacker:
    """TEMPORARY stand-in for the LLM attacker. Same interface: write_fake_site_code(context, feedback)."""

    attacker_id: str = "training"
    seed: int = 2026
    model: str = "scripted-v1..v4"
    kind: str = field(default="scripted", init=False)
    calls: list[LLMCall] = field(default_factory=list)
    _round: int = field(default=0, init=False)

    def write_fake_site_code(self, context: dict, feedback: dict | None) -> str:
        self._round += 1
        version = min(self._round, 4)
        self.calls.append(LLMCall(model=f"scripted-v{version}", provider="scripted", input_tokens=0, output_tokens=0, latency_s=0.0))
        return scripted_source(version)

    @property
    def last_call(self) -> LLMCall | None:
        return self.calls[-1] if self.calls else None

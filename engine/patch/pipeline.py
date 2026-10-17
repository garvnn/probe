"""Patch end to end: fit the learned check, gate it, recalibrate, and freeze Sentinel v1. Owner: Garv.

Data pools (all leaks-on Trial Twin trials, scenarios alternating A/B):
  fit         seeds 201-260   honest sites the learned check is fit on
  held-out    seeds 301-350   honest sites never used to fit or calibrate; false alarms are measured here
  calibration seeds 1-50      the v0 calibration pool; v1's threshold is set here (not on the fit pool,
                              where the model's in-sample scores would make the threshold look better)
Fakes: saved Impostor runs plus the scripted versions. LLM runs are split by run into train and
held-out; the scripted group always trains. The gate (engine.patch.gate) decides at the v0 threshold;
v1 is frozen only if the gate accepts AND the recalibrated suite still catches a clear majority of the
held-out escapes. A report is always written, frozen or not.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from engine.fraud_checks.calibrate import CALIBRATION_SEEDS, FALSE_ALARM_BUDGET, threshold_for
from engine.fraud_checks.checks_core import CORE_CHECKS
from engine.fraud_checks.suite import FROZEN_DIR, load_suite
from engine.patch import data
from engine.patch.fallback_check import FallbackClassifierCheck
from engine.patch.features import CHECK_FEATURES, feature_frame
from engine.patch.gate import CLEAR_MAJORITY, evaluate_gate, wilson

OWNER = "Garv"

REPORT_PATH = FROZEN_DIR / "patch_report.json"


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": int(k), "n": int(n), "rate": round(k / n, 4) if n else None, "ci95": [round(lo, 3), round(hi, 3)]}


def _row(name: str, threshold: float, real: np.ndarray, fakes_all: np.ndarray, escapes: np.ndarray) -> dict:
    return {
        "suite": name,
        "threshold": round(float(threshold), 4),
        "heldout_real_flagged": _rate(int((real >= threshold).sum()), len(real)),
        "heldout_fakes_caught": _rate(int((fakes_all >= threshold).sum()), len(fakes_all)),
        "heldout_v0_escapes_caught": _rate(int((escapes >= threshold).sum()), len(escapes)),
    }


def run_patch(
    cache_dir: Path | None = None,
    runner=None,
    write: bool = True,
    fit_seeds=data.FIT_SEEDS,
    holdout_seeds=data.HOLDOUT_SEEDS,
    calibration_seeds=CALIBRATION_SEEDS,
    scripted_seeds=data.SCRIPTED_SEEDS,
    extra_fakes: list[data.FakeRecord] | None = None,
) -> dict:
    """Run Patch and return the report. Writes frozen/v1.json only if accepted (and `write`)."""
    v0 = load_suite(0)
    if [c.name for c in v0.checks] != [c.name for c in CORE_CHECKS]:
        raise RuntimeError("Patch assumes v0 is the five core checks; v0 changed, so update the v0 score shortcut")

    def v0_scores(X: pd.DataFrame) -> np.ndarray:
        return X[list(CHECK_FEATURES)].max(axis=1).to_numpy()

    with data.temp_db():
        fit_pairs, hold_pairs = data.honest_pool(fit_seeds), data.honest_pool(holdout_seeds)
        fakes, skipped = data.load_fakes(cache_dir, runner)
        fakes += data.scripted_fakes(seeds=scripted_seeds) + list(extra_fakes or [])
        X_fit, X_hold = feature_frame(fit_pairs), feature_frame(hold_pairs)
        X_fake = feature_frame([(f.site, f.reference) for f in fakes])

        train_groups, held_groups = data.split_groups([f.group for f in fakes])
        is_held = np.array([f.group in held_groups for f in fakes])
        learned = FallbackClassifierCheck().fit_frames(X_fit, X_fake[~is_held])

        def candidate_scores(X: pd.DataFrame) -> np.ndarray:
            return np.maximum(v0_scores(X), learned.score_frame(X))

        fake_v0, fake_cand = v0_scores(X_fake), candidate_scores(X_fake)
        gate = evaluate_gate(v0.threshold, v0_scores(X_hold), candidate_scores(X_hold), fake_v0[is_held], fake_cand[is_held])
        held_escape = is_held & (fake_v0 < v0.threshold)

        rows = [_row("v0", v0.threshold, v0_scores(X_hold), fake_v0[is_held], fake_v0[held_escape])]
        frozen, final_status, t1 = False, gate.status, None
        if gate.accepted:
            X_cal = feature_frame(data.honest_pool(calibration_seeds))
            t1 = threshold_for(list(candidate_scores(X_cal)), FALSE_ALARM_BUDGET)
            v1_row = _row("v1", t1, candidate_scores(X_hold), fake_cand[is_held], fake_cand[held_escape])
            rows.append(v1_row)
            lo = v1_row["heldout_v0_escapes_caught"]["ci95"][0]
            if lo > CLEAR_MAJORITY:
                frozen, final_status = True, "accepted and frozen as v1"
            else:
                final_status = f"rejected after recalibration: threshold {t1:.3f} catches too few held-out escapes (95% lower bound {lo:.0%})"
        else:
            rows.append(_row("candidate (not frozen)", v0.threshold, candidate_scores(X_hold), fake_cand[is_held], fake_cand[held_escape]))

    by_source = pd.Series([f.source for f in fakes]).value_counts().to_dict()
    report = {
        "status": final_status,
        "frozen": frozen,
        "gate": gate.to_dict(),
        "table": rows,
        "learned_check": {"name": learned.name, "top_weights": learned.top_weights(), "C": learned.train_info["C"]},
        "data": {
            "fit_seeds": f"{fit_seeds.start}-{fit_seeds.stop - 1}",
            "holdout_seeds": f"{holdout_seeds.start}-{holdout_seeds.stop - 1}",
            "calibration_seeds": f"{calibration_seeds.start}-{calibration_seeds.stop - 1}",
            "n_fit_real": len(fit_pairs),
            "n_holdout_real": len(hold_pairs),
            "n_fakes": len(fakes),
            "fakes_by_source": by_source,
            "train_groups": sorted(train_groups),
            "heldout_groups": sorted(held_groups),
            "n_train_fakes": int((~is_held).sum()),
            "n_heldout_fakes": int(is_held.sum()),
            "train_fakes_caught_in_sample": _rate(int((fake_cand[~is_held] >= v0.threshold).sum()), int((~is_held).sum())),
            "skipped_rounds": skipped,
        },
        "date": date.today().isoformat(),
    }
    if write:
        FROZEN_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n")
        if frozen:
            v1 = {
                "version": 1,
                "parent": 0,
                "checks": [*[c.name for c in v0.checks], learned.name],
                "check_params": {learned.name: learned.to_params()},
                "threshold": round(float(t1), 6),
                "combined": "max",
                "flag_rule": "combined >= threshold",
                "budget": FALSE_ALARM_BUDGET,
                "added": {"check": learned.name, "created_by": "fallback", "kind": "regularized logistic regression on site-level features"},
                "gate": gate.to_dict(),
                "table": rows,
                "data": report["data"],
                "frozen_on": report["date"],
            }
            (FROZEN_DIR / "v1.json").write_text(json.dumps(v1, indent=2, default=str) + "\n")
    return report

"""Run Tell and Seal on real simulator trials and save the results for the cached demo. Owner: Ajay.

    python -m scripts.run_tell tell      # Scenario A + mechanisms-off control, coordinator view -> tell_tr_2026_A.json
    python -m scripts.run_tell seal      # all 16 remedy combos on Scenario A, coordinator view -> seal_tr_2026_A.json
    python -m scripts.run_tell assessor  # Scenario B assessor view, printed and written to --out only (not cached)

Uses only the documented entry points: generate_trial, export_view, and (for labels) evals.scoring.
The control must come out at chance; if it doesn't, the script exits non-zero and saves nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from engine.blind_leak import cache
from engine.blind_leak.cheapest_fix import ACCEPTANCE_RULE, best_partial, evaluate_combos
from engine.blind_leak.permutation import DEFAULT_N
from engine.blind_leak.remedies import COSTS_ARE_ASSIGNED
from engine.blind_leak.result import BlindResult, run_blind
from evals.scoring import arm_labels

UTILITY_FLOOR = 0.90


def trial(scenario: str, mechanisms_off: bool = False) -> str:
    from engine.simulator.trial import TrialConfig, generate_trial

    cfg = TrialConfig(scenario=scenario, mechanisms={}) if mechanisms_off else TrialConfig(scenario=scenario)
    return generate_trial(cfg).trial_id


def tell_payload(r: BlindResult, trial_id: str, view: str, scenario: str, mechanisms: str) -> dict:
    return {
        "_mock": False,
        "trial_id": trial_id,
        "view": view,
        "remedies": [],
        "scenario": scenario,
        "mechanisms": mechanisms,
        "accuracy": r.accuracy,
        "auc": r.auc,
        "null_lo": r.null_lo,
        "null_hi": r.null_hi,
        "p_value": r.p_value,
        "p_value_auc": r.p_value_auc,
        "n_permutations": r.n_permutations,
        "null_accuracy": r.null_accuracy,
        "seed": r.seed,
        "blind_holds": r.blind_holds,
        "utility": r.utility,
        "top_leaks": r.top_leaks,
        "folds": r.folds,
    }


def run_view(trial_id: str, view: str, n: int, seed: int) -> BlindResult:
    from engine.simulator.views import export_view

    t0 = time.time()
    r = run_blind(export_view(trial_id, view), trial_id, n_permutations=n, seed=seed, top=6)
    print(f"{trial_id} {view}: acc={r.accuracy:.3f} auc={r.auc:.3f} null95=[{r.null_lo:.3f},{r.null_hi:.3f}] "
          f"p={r.p_value:.4f} blind_holds={r.blind_holds} ({time.time() - t0:.0f}s)", flush=True)
    return r


def cmd_tell(args) -> int:
    a_id, c_id = trial("A"), trial("A", mechanisms_off=True)
    a = run_view(a_id, "coordinator", args.n, args.seed)
    c = run_view(c_id, "coordinator", args.n, args.seed)
    if not c.blind_holds:
        print("BUG: mechanisms-off control is not at chance. Not saving; this is not a finding.", file=sys.stderr)
        return 1
    payload = tell_payload(a, a_id, "coordinator", "A", "default")
    payload["control"] = tell_payload(c, c_id, "coordinator", "A", "off")
    payload["created_at"] = datetime.now(timezone.utc).isoformat()
    print("saved", cache.save("tell", a_id, payload))
    return 0


def cmd_seal(args) -> int:
    from engine.simulator.views import export_view

    a_id = trial("A")
    t0 = time.time()

    def progress(i, combo, row):
        print(f"[{i + 1:2d}/16 {time.time() - t0:5.0f}s] {'+'.join(combo) or 'none':<62} acc={row['accuracy']:.3f} "
              f"auc={row['auc']:.3f} p={row['p_value']:.4f} util={row['utility']:.3f} cost={row['cost']:.0f} "
              f"acceptable={row['acceptable']}", flush=True)

    rec, rows = evaluate_combos(lambda combo: export_view(a_id, "coordinator", remedies=combo), arm_labels(a_id),
                                utility_floor=UTILITY_FLOOR, n_permutations=args.n, seed=args.seed, progress=progress)
    payload = {
        "_mock": False,
        "trial_id": a_id,
        "view": "coordinator",
        "utility_floor": UTILITY_FLOOR,
        # Display line for the plot only: the no-remedy run's AUC null 97.5th percentile. Acceptance uses ACCEPTANCE_RULE.
        "auc_ceiling": rows[0]["null_auc_hi"],
        "acceptance_rule": ACCEPTANCE_RULE.format(floor=UTILITY_FLOOR),
        "costs_are_assigned": COSTS_ARE_ASSIGNED,
        "n_permutations": args.n,
        "seed": args.seed,
        "recommended": rec,
        "best_partial": None if rec else best_partial(rows),
        "results": rows,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    print("recommended:", json.dumps(rec) if rec else "NONE ACCEPTABLE")
    print("saved", cache.save("seal", a_id, payload))
    return 0


def cmd_assessor(args) -> int:
    b_id = trial("B")
    b = run_view(b_id, "assessor", args.n, args.seed)
    payload = tell_payload(b, b_id, "assessor", "B", "default")
    for leak in b.top_leaks:
        print(f"  {leak['field']:<50} share={leak['importance']:.3f} drop_auc={leak['drop_auc']:+.4f}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(payload, f, indent=2)
        print("wrote", args.out, "(review copy, not cached for the UI)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["tell", "seal", "assessor"])
    p.add_argument("--n", type=int, default=DEFAULT_N, help="permutations per run")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", help="assessor: where to write the review JSON")
    args = p.parse_args()
    return {"tell": cmd_tell, "seal": cmd_seal, "assessor": cmd_assessor}[args.what](args)


if __name__ == "__main__":
    sys.exit(main())

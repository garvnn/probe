"""Precompute measured demo responses without running an attacker or refitting Patch.

Usage: DEMO_SEED=2026 .venv/bin/python -m scripts.precompute_demo
The existing tr_2026_B database must be present at DB_PATH. No generation fallback.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

TRIAL_ID = "tr_2026_B"
DEMO_SEED = 2026
RUN_ID = "fd_20261017T202527_llm_s43"
OWNER = "Shreyas"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class ResponseCache:
    def __init__(self, out: Path):
        self.out = out
        self.responses: dict[str, list] = {}
        self.written: list[str] = []

    def save(self, name: str, payload: dict, request: dict, filename: str | None = None):
        filename = filename or f"{name}.json"
        payload = {**payload, "_mock": False}
        write(self.out / "precomputed" / filename, payload)
        self.responses.setdefault(name, []).append({"path": filename, "request": request})
        self.written.append(str(self.out / "precomputed" / filename))
        print(f"WROTE {self.written[-1]}", flush=True)
        return payload


def saved_escapes(run: dict):
    """Deserialize saved rows only. Never execute saved attacker source."""
    import pandas as pd
    from engine.fraud_checks.base import SiteData

    sites = []
    for rnd in run["rounds"]:
        if not (rnd["ok"] and rnd["escaped"]):
            continue
        output = rnd.get("fake_output")
        if not output or not output.get("ground_truth"):
            raise ValueError(f"escaped round {rnd['round']} has no saved site/own arm split")
        tables = {name: pd.DataFrame(rows) for name, rows in output.items() if name != "ground_truth"}
        # Empty tables still require documented columns for the existing scoring helpers.
        for name, cols in {"adverse_events": ["ae_id", "patient_id", "term", "category", "onset_date", "severity"],
                           "conmeds": ["patient_id", "drug_class", "start_date"],
                           "kit_storage": ["event_id", "patient_id", "kit_id", "date", "event_type", "storage", "temp_c"]}.items():
            if tables[name].empty:
                tables[name] = pd.DataFrame(columns=cols)
        for frame in tables.values():
            for col in ("date", "onset_date", "start_date"):
                if col in frame:
                    frame[col] = pd.to_datetime(frame[col])
        arms = pd.DataFrame(output["ground_truth"]).set_index("patient_id")["arm"]
        sites.append((rnd["round"], SiteData(run["fake_site_id"], tables, arms)))
    return sites


def trial_math(run: dict, trial):
    """Existing frozen suites + saved fakes; no new fake generation or suite tuning."""
    from engine.analysis.damage import effect_shift
    from engine.analysis.breaking_point import breaking_point
    from engine.fake_data.sites import split_sites
    from engine.fraud_checks.suite import load_suite

    escaped = saved_escapes(run)
    real = split_sites(trial)
    damages = [{"round": rnd, **asdict(effect_shift(trial, [site]))} for rnd, site in escaped]
    curves = {}
    accepted = {}
    for version in (0, 1):
        suite = load_suite(version)
        accepted[version] = [(rnd, site) for rnd, site in escaped if not suite.flags(site, real)]
        curve, break_k = breaking_point(trial, [site for _, site in accepted[version]], max_k=6)
        curves[version] = {"_mock": False, "trial_id": TRIAL_ID, "suite_version": version,
                           "curve": curve, "break_k": break_k}
    return damages, curves, {str(v): [r for r, _ in rows] for v, rows in accepted.items()}


def assemble_contract(run, tell, damage):
    changed = any(abs(row["effect_with_fake"] - row["effect_real"]) > 1e-12 for row in damage)
    leaks = tell["p_value"] < .05 and tell["accuracy"] > tell["null_hi"]
    return [
        {"name": "data_authenticity", "status": "broken", "counterexample":
         f"Saved run {run['run_id']} contains {sum(r['ok'] and r['escaped'] for r in run['rounds'])} v0 escape rounds; rounds are adaptive, not independent."},
        {"name": "treatment_confidentiality", "status": "broken" if leaks else "untested",
         "counterexample": f"Coordinator accuracy {tell['accuracy']:.5f}, AUC {tell['auc']:.5f}, permutation p={tell['p_value']:.5f}." if leaks else None},
        {"name": "statistical_integrity", "status": "broken" if changed else "untested",
         "counterexample": "Saved escaped fakes changed the ANCOVA effect estimate; this alone does not establish a conclusion flip." if changed else None},
        {"name": "safety_accessibility", "status": "untested", "counterexample": None},
        {"name": "operational_utility", "status": "untested", "counterexample": None},
    ]


def precompute(out: Path) -> dict:
    from engine.blind_leak.result import run_blind
    # Allowed public boundary. Never inspect simulator implementation.
    from engine.simulator.views import export_view

    cache = ResponseCache(out)
    skipped = []
    source = ROOT / "data/demo_cache" / f"{RUN_ID}.json"
    run = read(source)
    if run.get("not_a_result") is not False or run["suite"].get("standin") is not False:
        raise ValueError("locked Impostor run is not measured")
    if run["trial_id"] != TRIAL_ID or run["attacker"]["seed"] != 43 or not any(r["round"] == 7 and r["escaped"] for r in run["rounds"]):
        raise ValueError("wrong locked Impostor run / missing displayed round-8 escape")
    run = {**run, "_mock": False}
    write(out / f"{RUN_ID}.json", run)
    print(f"REUSED {out / (RUN_ID + '.json')} (no attacker invoked)", flush=True)

    frozen = read(ROOT / "engine/fraud_checks/frozen/patch_report.json")
    table = {r["suite"]: r for r in frozen["table"]}
    before, after = table["v0"], table["v1"]
    caught = after["heldout_v0_escapes_caught"]
    patch = cache.save("patch", {
        "new_version": 1, "status": frozen["gate"]["status"], "created_by": "fallback",
        "check_name": frozen["learned_check"]["name"],
        "check_source": (ROOT / "engine/patch/fallback_check.py").read_text(),
        "caught": caught["k"], "n_escaped": caught["n"],
        # Use the final frozen suite table, not the pre-recalibration gate rate.
        "fp_before": before["heldout_real_flagged"]["rate"],
        "fp_after": after["heldout_real_flagged"]["rate"],
    }, {"trial_id": TRIAL_ID, "run_id": RUN_ID, "suite_version": 0})
    cache.save("patch_held_out", {**frozen, "trial_id": TRIAL_ID,
        "evidence_note": "Every v0 escape caught across 4 held-out runs; adaptive rounds within a run are not independent. Not a different-model attacker evaluation."}, {"trial_id": TRIAL_ID})

    print("MEASURING Tell coordinator (200 within-site permutations)", flush=True)
    result = run_blind(export_view(TRIAL_ID, "coordinator", remedies=[]), TRIAL_ID, seed=DEMO_SEED)
    tell = cache.save("blind_leak_run", {"trial_id": TRIAL_ID, "view": "coordinator", "remedies": [], **asdict(result)},
                      {"trial_id": TRIAL_ID, "view": "coordinator"})
    from engine.blind_leak.cheapest_fix import cheapest_fix
    try:
        # Main's stub has a required remedies argument; supplying it detects the stub
        # without reading its implementation. Completed Seal uses the new signature.
        import inspect
        args = {"remedies": ["unblinded_pharmacist", "sham_titration", "central_lab", "matched_kits"]} if "remedies" in inspect.signature(cheapest_fix).parameters else {}
        recommended, rows = cheapest_fix(TRIAL_ID, **args)
    except NotImplementedError:
        skipped.append("Seal: cheapest_fix is still a stub on main; cheapest-fix and policy remain badged samples")
    else:
        cache.save("blind_leak_cheapest_fix", {"trial_id": TRIAL_ID, "utility_floor": .9, "auc_ceiling": .55,
            "costs_are_assigned": True, "recommended": recommended, "results": rows},
            {"trial_id": TRIAL_ID, "utility_floor": .9, "auc_ceiling": .55})
        if recommended is not None:
            policy = run_blind(export_view(TRIAL_ID, "assessor", remedies=recommended["combo"]), TRIAL_ID,
                               seed=DEMO_SEED, utility=recommended["utility"])
            cache.save("blind_leak_policy", {"trial_id": TRIAL_ID, "view": "assessor", "remedies": recommended["combo"], **asdict(policy)},
                       {"trial_id": TRIAL_ID, "view": "assessor", "remedies": recommended["combo"]})

    # User-authorized exception: public load_trial only for trial math. No simulator source is read.
    from engine.simulator.trial import load_trial
    trial = load_trial(TRIAL_ID)
    if trial.config.seed != DEMO_SEED or trial.config.scenario != "B":
        raise ValueError("existing trial does not match locked seed/scenario")
    damage, curves, accepted = trial_math(run, trial)
    cache.save("damage", {"trial_id": TRIAL_ID, "run_id": RUN_ID, "rounds": damage,
                           "accepted_saved_rounds": accepted, "available_escaped_sites": len(damage),
                           "note": "Only saved escaped sites used, once each. No extrapolation beyond their count."}, {"trial_id": TRIAL_ID})
    for version, curve in curves.items():
        cache.save("breaking_point", curve, {"trial_id": TRIAL_ID, "suite_version": version, "max_k": 6}, f"breaking_point_v{version}.json")
    properties = assemble_contract(run, tell, damage)
    contract = cache.save("contract_untested", {"trial_id": TRIAL_ID, "properties": properties}, {"trial_id": TRIAL_ID}, "contract.json")
    cache.responses["contract_mixed"] = cache.responses["contract_untested"]
    report = {"trial_id": TRIAL_ID, "contract": properties,
        "headlines": [
            {"label": "Frozen held-out v0 escapes caught (4 runs)", "before": f"0 / {patch['n_escaped']}", "after": f"{patch['caught']} / {patch['n_escaped']}"},
            {"label": "Frozen honest-site false alarms", "before": f"{patch['fp_before']:.1%}", "after": f"{patch['fp_after']:.1%}"},
            {"label": "Coordinator prediction (no policy change measured)", "before": f"Accuracy {tell['accuracy']:.3%}", "after": f"AUC {tell['auc']:.5f}"}],
        "breaking_point_v0": curves[0], "breaking_point_vN": curves[1],
        "fixes": ["Frozen Sentinel v1: every v0 escape caught across 4 held-out runs; rounds are not independent.",
                  "v1 has not been tested against a different-model attacker.",
                  "Breaking-point null means no flip among the available saved sites; it is not evidence beyond that range."] + skipped}
    cache.save("report", report, {"trial_id": TRIAL_ID})
    skipped.extend(["Stranger: no measured different-model results on main; endpoint remains sample data",
                    "Guess Who: cards and scoring not precomputed; endpoints remain sample data",
                    "Trial setup: trial-summary/detail routes remain sample data"])
    index = {"_mock": False, "trial_id": TRIAL_ID, "seed": DEMO_SEED, "run_id": RUN_ID,
             "source_sha256": {"impostor": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "patch_report": hashlib.sha256((ROOT / "engine/fraud_checks/frozen/patch_report.json").read_bytes()).hexdigest()},
             "responses": cache.responses, "skipped": skipped}
    write(out / "precomputed/manifest.json", index)
    for note in skipped:
        print(f"SKIPPED {note}", flush=True)
    print(f"DONE: reused 1 run; wrote {len(cache.written)} response files + manifest", flush=True)
    return index


def main(argv: list[str] | None = None) -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=int(os.environ.get("DEMO_SEED", "2026")))
    parser.add_argument("--scenario", choices=["A", "B"], default="B")
    parser.add_argument("--out", type=Path, default=Path(os.environ.get("DEMO_CACHE_DIR", "data/demo_cache")))
    args = parser.parse_args(argv)
    if args.seed != DEMO_SEED or args.scenario != "B":
        parser.error("this cache is locked to tr_2026_B / DEMO_SEED=2026")
    precompute(args.out)


if __name__ == "__main__":
    main()

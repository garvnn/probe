"""Post-freeze Stranger evaluation. Never executes saved attacker source. Owner: Shreyas."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from engine.fake_data.attacker import PROMPT_FOR_ROLE
from engine.fake_data.cache import cache_dir
from integrations.llm import model_for

FROZEN = Path(__file__).resolve().parents[1] / "fraud_checks" / "frozen"


def frozen_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((FROZEN / name).read_bytes()).hexdigest()
            for name in ("v0.json", "v1.json", "patch_report.json")}


def assert_test_ready(seed: int) -> None:
    report = json.loads((FROZEN / "patch_report.json").read_text())
    if not report.get("frozen") or not report.get("gate", {}).get("accepted"):
        raise ValueError("Patch must be accepted and frozen before Stranger")
    frozen_hashes()
    if model_for("test") == model_for("training"):
        raise ValueError("Stranger must use a different model from training")
    if PROMPT_FOR_ROLE["test"].read_bytes() == PROMPT_FOR_ROLE["training"].read_bytes():
        raise ValueError("Stranger must use a different prompt")
    for path in cache_dir().glob("fd_*.json"):
        run = json.loads(path.read_text())
        attacker = run.get("attacker", {})
        if attacker.get("id") != "training" or run.get("not_a_result", True):
            continue
        if attacker.get("seed") == seed:
            raise ValueError(f"Stranger seed {seed} was used for training in {path.name}")
        if attacker.get("model") == model_for("test"):
            raise ValueError("Stranger model was already used for training")


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    z = 1.959963984540054
    p = k / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return max(0.0, center-half), min(1.0, center+half)


def score_runs(runs: list[dict], trial, versions=(0, 1)) -> dict:
    """Paired rescoring of saved outputs; run-level any-escape is the primary endpoint."""
    from engine.fake_data.sites import split_sites
    from engine.fake_data.validate import validate_schema
    from engine.fraud_checks.suite import load_suite

    if not runs:
        raise ValueError("No Stranger runs supplied")
    hashes = frozen_hashes()
    reference = split_sites(trial)
    seen = set()
    budgets = {r.get("rounds_planned") for r in runs}
    if len(budgets) != 1:
        raise ValueError("Stranger runs must share one fixed round budget")
    prompts = {r.get("attacker", {}).get("prompt_sha256") for r in runs}
    if len(prompts) != 1 or None in prompts:
        raise ValueError("Stranger evaluation requires one frozen prompt")
    models = {r.get("attacker", {}).get("model") for r in runs}
    if len(models) != 1 or None in models:
        raise ValueError("Stranger evaluation requires one test model")
    for run in runs:
        a = run.get("attacker", {})
        if (a.get("id") != "test" or a.get("kind") != "llm"
                or run.get("not_a_result", True) or run.get("runner") != "DaytonaRunner"):
            raise ValueError("Only measured Stranger Daytona runs can be scored")
        if run.get("trial_id") != trial.trial_id or run.get("suite", {}).get("version") != 0:
            raise ValueError("Stranger requires the requested trial and v0-only feedback")
        if run.get("frozen_sha256") != hashes:
            raise ValueError("Frozen artifacts changed or run lacks freeze provenance")
        if not run.get("rounds") or len(run["rounds"]) != run.get("rounds_planned"):
            raise ValueError("Only completed fixed-budget runs can be scored")
        if not any(r.get("sandbox_id") for r in run["rounds"]):
            raise ValueError("Provider/infrastructure failures with no sandbox execution are not evaluations")
        identity = (a.get("model"), a.get("prompt_sha256"), a.get("seed"))
        if identity in seen:
            raise ValueError("Duplicate model/prompt/seed run")
        seen.add(identity)
        if not a.get("model") or a.get("seed") is None:
            raise ValueError("Stranger model and seed provenance are required")
    rows, per_run = [], []
    for version in versions:
        suite = load_suite(version)
        run_escapes = 0
        for run in runs:
            valid = escaped = errors = 0
            for rnd in run["rounds"]:
                if not rnd.get("ok"):
                    errors += 1
                    continue
                if not rnd.get("fake_output"):
                    raise ValueError("Valid round lacks saved fake_output; source will not be executed")
                fake = validate_schema(rnd["fake_output"], run["fake_site_id"])
                score = suite.score_site(fake, reference)
                valid += 1
                escaped += int(score.combined < suite.threshold)
            run_escapes += int(escaped > 0)
            per_run.append({"run_id": run["run_id"], "suite_version": version,
                            "attempted_rounds": len(run["rounds"]), "valid_rounds": valid,
                            "error_rounds": errors, "escaped_rounds": escaped})
        n = len(runs)
        rows.append({"suite_version": version, "attacker_id": "test", "attempted": n,
                     "escaped": run_escapes, "evasion_rate": run_escapes/n,
                     "ci95": wilson(run_escapes, n), "fp_rate": suite.false_alarm_rate(reference)})
    limitations = ["Run-level Wilson intervals are exploratory with few runs.",
                   "Gemini sampling is not seed-deterministic; recorded seeds control generated-site randomness."]
    limitations.extend(dict.fromkeys(r["recovery_note"] for r in runs if r.get("recovery_note")))
    if any(row["suite_version"] == 0 and row["escaped"] == 0 for row in rows):
        limitations.append("No v0 run had an escape at this budget; this batch cannot establish improved escape detection by v1.")
    return {"_mock": False, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "trial_id": trial.trial_id, "attacker_id": "test",
            "evaluation_unit": "runs", "round_budget": next(iter(budgets)), "model": next(iter(models)),
            "never_seen_during_patching": True, "rows": rows, "per_run": per_run,
            "frozen_sha256": hashes, "run_ids": [r["run_id"] for r in runs],
            "endpoint": "any valid escape within a fixed-budget run; attempted/escaped count runs",
            "fp_population": "honest sites in the requested trial, not the Patch held-out cohort",
            "limitations": limitations}


def report_path() -> Path:
    return cache_dir() / "stranger_report.json"

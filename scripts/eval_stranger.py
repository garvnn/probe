"""Score completed Stranger runs against frozen v0/v1 without executing attacker code.

Example: .venv/bin/python scripts/eval_stranger.py fd_<test_run_id> [fd_<other_run_id>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from engine.fake_data.cache import load_run
    from engine.fake_data.stranger import report_path, score_runs
    from engine.simulator.trial import TrialConfig, generate_trial
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_ids", nargs="+")
    args = parser.parse_args()
    runs = [load_run(r) for r in args.run_ids]
    first = runs[0]
    for run in runs:
        if (run["trial_seed"], run["scenario"], run["rounds_planned"]) != (first["trial_seed"], first["scenario"], first["rounds_planned"]):
            raise ValueError("Use runs with the same trial and fixed round budget")
    trial = generate_trial(TrialConfig(scenario=first["scenario"], seed=first["trial_seed"]))
    report = score_runs(runs, trial)
    path = report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2))
    temporary.replace(path)
    print(json.dumps(report, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()

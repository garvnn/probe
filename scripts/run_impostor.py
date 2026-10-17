"""Run one Impostor (fake-data) loop end to end and print a table per round. Owner: Shreyas.

Generates the Trial Twin, calibrates the check suite on its real sites, then lets the attacker
fabricate a site for `--rounds` rounds. Every round runs in a fresh Daytona sandbox and is saved
to data/demo_cache/<run_id>.json, which DEMO_MODE=cached replays through the API.

The check suite is the TEMPORARY stand-in (engine/fraud_checks/_standin.py) until Sentinel lands.
With no LLM key in .env the attacker is the TEMPORARY scripted one. Runs using either are
labeled "not a result" in the saved file and in the API (`_mock: true`).

Usage:
    .venv/bin/python scripts/run_impostor.py                     # scripted if no key, 8 rounds
    .venv/bin/python scripts/run_impostor.py --attacker llm --rounds 8
    .venv/bin/python scripts/run_impostor.py --runner mock       # no Daytona key; never runs the code
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

OWNER = "Shreyas"

HEADER = f"{'round':>5}  {'attacker':<16} {'attacker s':>10} {'sandbox s':>9}  {'ok':<5} {'combined':>8} {'threshold':>9}  {'result':<9} fired / error"


def row(rnd) -> str:
    combined = f"{rnd.combined:8.2f}" if rnd.combined is not None else f"{'-':>8}"
    detail = ", ".join(rnd.fired) if rnd.ok else (rnd.error or "").strip().splitlines()[-1][:70] if rnd.error else ""
    who = rnd.attacker_model[:16]
    return (
        f"{rnd.round + 1:>5}  {who:<16} {rnd.attacker_s:10.2f} {rnd.sandbox_s:9.2f}  {str(rnd.ok):<5} "
        f"{combined} {rnd.threshold:9.2f}  {rnd.status.upper():<9} {detail}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--attacker", choices=["auto", "scripted", "llm"], default="auto", help="auto = llm if a key is set, else scripted")
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--scenario", choices=["A", "B"], default="B")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--runner", choices=["daytona", "mock"], default="daytona", help="mock never executes the code (wiring only)")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--stop-on-escape", action="store_true")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    from engine.fake_data.attacker import make_attacker
    from engine.fake_data.cache import run_path
    from engine.fake_data.loop import fake_data_loop
    from engine.fake_data.sites import split_sites
    from engine.fraud_checks._standin import calibrate_standin
    from engine.simulator.trial import TrialConfig, generate_trial
    from integrations.daytona import DaytonaRunner, LocalMockRunner

    trial = generate_trial(TrialConfig(scenario=args.scenario, seed=args.seed))
    real_sites = split_sites(trial)
    suite = calibrate_standin(real_sites)
    attacker = make_attacker("training", kind=args.attacker, seed=args.seed)
    runner = DaytonaRunner(reuse=False) if args.runner == "daytona" else LocalMockRunner()
    run_id = f"fd_{time.strftime('%Y%m%dT%H%M%S')}_{attacker.kind}"

    print(f"trial {trial.trial_id}: {len(real_sites)} real sites; suite '{suite.name}' threshold {suite.threshold} (false alarms {suite.false_alarm_rate(real_sites):.0%})")
    print(f"attacker: {attacker.kind} ({attacker.model}); runner: {type(runner).__name__}; run {run_id}\n")
    print(HEADER)
    t = time.perf_counter()
    rounds = fake_data_loop(
        trial, suite, attacker, args.rounds, runner=runner, real_sites=real_sites, run_id=run_id,
        timeout=args.timeout, stop_on_escape=args.stop_on_escape, on_round=lambda r: print(row(r), flush=True),
    )
    wall = time.perf_counter() - t

    sandbox = [r.sandbox_s for r in rounds if r.sandbox_id]
    attacker_s = [r.attacker_s for r in rounds]
    print(
        f"\ntotals: {len(rounds)} rounds | escaped {sum(r.escaped for r in rounds)} | detected {sum(r.status == 'detected' for r in rounds)} | "
        f"errors {sum(r.status == 'error' for r in rounds)}\n"
        f"        attacker {sum(attacker_s):.2f}s (mean {statistics.mean(attacker_s):.2f}s) | "
        f"sandbox exec {sum(sandbox):.2f}s (mean {statistics.mean(sandbox) if sandbox else 0:.2f}s) | "
        f"wall {wall:.2f}s (mean {wall / len(rounds):.2f}s per round)"
    )
    sequence = ", ".join(r.status for r in rounds)
    print(f"sequence: {sequence}")
    print(f"saved {run_path(run_id)}")
    if attacker.kind == "scripted" or suite.name.startswith("standin"):
        print("NOTE: stand-in checks and/or scripted attacker. This run is not a result.")


if __name__ == "__main__":
    main()

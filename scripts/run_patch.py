"""Patch: fit the learned check, gate it, and freeze Sentinel v1 if it passes. Owner: Garv.

Prints v0 vs v1 (or the unfrozen candidate): false alarms on held-out real sites, held-out fakes
caught, and held-out v0 escapes caught, with counts and Wilson 95% intervals. Always writes
engine/fraud_checks/frozen/patch_report.json; writes v1.json only if the gate accepts.

Fakes come from saved Impostor runs in data/demo_cache/ (copy teammates' fd_*.json files there) plus
the scripted versions. Rounds saved before fake sites were stored need --runner daytona to re-run
their code in a sandbox; LLM-written code never runs on this machine.

Usage:
    .venv/bin/python scripts/run_patch.py
    .venv/bin/python scripts/run_patch.py --runner daytona       # rebuild old rounds in Daytona
    .venv/bin/python scripts/run_patch.py --dry-run              # print, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

OWNER = "Garv"


def _cell(r: dict) -> str:
    if not r["n"]:
        return "0/0 (no data)"
    lo, hi = r["ci95"]
    return f"{r['k']}/{r['n']} = {r['rate']:.1%} [{lo:.1%}, {hi:.1%}]"


def print_report(report: dict) -> None:
    d, g = report["data"], report["gate"]
    print(f"honest sites: fit {d['n_fit_real']} (seeds {d['fit_seeds']}), held-out {d['n_holdout_real']} (seeds {d['holdout_seeds']}), "
          f"calibration seeds {d['calibration_seeds']}")
    print(f"fakes: {d['n_fakes']} ({', '.join(f'{v} {k}' for k, v in d['fakes_by_source'].items())}); "
          f"train {d['n_train_fakes']} from {len(d['train_groups'])} group(s), held-out {d['n_heldout_fakes']} from {len(d['heldout_groups'])} run(s)")
    if d["skipped_rounds"]:
        print(f"skipped {len(d['skipped_rounds'])} round(s):")
        for note in d["skipped_rounds"][:10]:
            print(f"  - {note}")
    print()
    head = f"{'suite':<24} {'threshold':>9}  {'held-out real flagged':<30} {'held-out fakes caught':<30} {'held-out v0 escapes caught':<30}"
    print(head)
    print("-" * len(head))
    for row in report["table"]:
        print(f"{row['suite']:<24} {row['threshold']:>9.3f}  {_cell(row['heldout_real_flagged']):<30} "
              f"{_cell(row['heldout_fakes_caught']):<30} {_cell(row['heldout_v0_escapes_caught']):<30}")
    print()
    print(f"gate (at v0 threshold {g['threshold']:.3f}): false alarms {g['flagged_before']}/{g['n_real']} -> {g['flagged_after']}/{g['n_real']}; "
          f"held-out escapes caught {g['caught']}/{g['n_escaped']}")
    for reason in g["reasons"]:
        print(f"  - {reason}")
    print(f"\nSTATUS: {report['status']}")
    print("learned check, strongest 'looks fake' weights: " + ", ".join(f"{n} ({w:+.2f})" for n, w in report["learned_check"]["top_weights"][:5]))
    tr = d["train_fakes_caught_in_sample"]
    print(f"(in-sample, not evidence: training fakes caught {_cell(tr)})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runner", choices=["none", "daytona"], default="none", help="re-run old rounds' code in Daytona")
    parser.add_argument("--cache-dir", type=Path, default=None, help="saved runs (default: $DEMO_CACHE_DIR or data/demo_cache)")
    parser.add_argument("--dry-run", action="store_true", help="print the report without writing anything")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    from engine.patch.pipeline import REPORT_PATH, run_patch

    runner = None
    if args.runner == "daytona":
        from integrations.daytona import DaytonaRunner

        runner = DaytonaRunner(reuse=False)
    report = run_patch(cache_dir=args.cache_dir, runner=runner, write=not args.dry_run)
    print_report(report)
    if not args.dry_run:
        print(f"\nwrote {REPORT_PATH}" + (" and v1.json" if report["frozen"] else " (v1.json not written)"))


if __name__ == "__main__":
    main()

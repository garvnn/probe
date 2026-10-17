"""Run the scenario suite and write the metrics table. Owner: Ajay.

Runs every scenario in evals.scenarios.SCENARIOS (ideally across 3+ seeds) and logs each metric
through evals.metrics.log_metric.

Usage:
    python scripts/run_full_eval.py --seeds 2026 2027 2028
"""

from __future__ import annotations

import argparse

OWNER = "Ajay"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, nargs="+", default=[2026])
    parser.add_argument("--scenarios", nargs="+", default=None, help="Subset of evals.scenarios.SCENARIOS")
    parser.parse_args(argv)
    raise NotImplementedError(f"owner: {OWNER}")


if __name__ == "__main__":
    main()

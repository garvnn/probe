"""Run the full demo with the locked seed and cache every result for DEMO_MODE=cached. Owner: Shreyas.

Caches each round's code, scores, and results into data/demo_cache/ so the UI can replay the run
through the same SSE stream at real speed if the APIs fail on stage.

Usage:
    python scripts/precompute_demo.py --seed 2026 --scenario B
"""

from __future__ import annotations

import argparse
from pathlib import Path

OWNER = "Shreyas"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--scenario", choices=["A", "B"], default="B")
    parser.add_argument("--out", type=Path, default=Path("data/demo_cache"))
    parser.parse_args(argv)
    raise NotImplementedError(f"owner: {OWNER}")


if __name__ == "__main__":
    main()

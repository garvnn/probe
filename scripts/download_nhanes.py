"""Download the NHANES files the generator needs into data/raw/. Owner: Garv.

Files: DEMO, GHB, GLU, BMX, BPX/BPXO for one recent cycle. Exact file names change between
cycles; verify them before relying on this script.

Usage:
    python scripts/download_nhanes.py --cycle 2017-2018 --out data/raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

OWNER = "Garv"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycle", required=True, help="NHANES cycle, e.g. 2017-2018")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.parse_args(argv)
    raise NotImplementedError(f"owner: {OWNER}")


if __name__ == "__main__":
    main()
